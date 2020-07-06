
#include <csignal>
#include <cpp_redis/cpp_redis>
#include <mutex>
#include <thread>
#include <sstream>
#include <set>

#include "../AmqpLibeventHandler.h"
#include "../ClientPool.h"
#include "../RedisClient.h"
#include "../ThriftClient.h"
#include "../logger.h"
#include "../tracing.h"
#include "../utils.h"
#include "../../gen-cpp/social_network_types.h"
#include "../../gen-cpp/SocialGraphService.h"

#define NUM_WORKERS 32

using namespace social_network;

static std::exception_ptr _teptr;
static ClientPool<RedisClient> *_redis_client_pool;
static ClientPool<ThriftClient<SocialGraphServiceClient>>
    *_social_graph_client_pool;


#include <iostream>

void sigintHandler(int sig) {
  exit(EXIT_SUCCESS);
}

void OnReceivedWorker(const AMQP::Message &msg) {
  try {
    json msg_json = json::parse(std::string(msg.body(), msg.bodySize()));

    std::map<std::string, std::string> carrier;
    for (auto it = msg_json["carrier"].begin();
        it != msg_json["carrier"].end(); ++it) {
      carrier.emplace(std::make_pair(it.key(), it.value()));
    }

    // Jaeger tracing
    TextMapReader span_reader(carrier);
    auto parent_span = opentracing::Tracer::Global()->Extract(span_reader);
    auto span = opentracing::Tracer::Global()->StartSpan(
        "FanoutHomeTimelines",
        {opentracing::ChildOf(parent_span->get())});
    std::map<std::string, std::string> writer_text_map;
    TextMapWriter writer(writer_text_map);
    opentracing::Tracer::Global()->Inject(span->context(), writer);

    // Extract information from rabbitmq messages
    int64_t user_id = msg_json["user_id"];
    int64_t req_id = msg_json["req_id"];
    int64_t post_id = msg_json["post_id"];
    int64_t timestamp = msg_json["timestamp"];
    std::vector<int64_t> user_mentions_id = msg_json["user_mentions_id"];

    // Find followers of the user
    auto social_graph_client_wrapper = _social_graph_client_pool->Pop();
    if (!social_graph_client_wrapper) {
      ServiceException se;
      se.errorCode = ErrorCode::SE_THRIFT_CONN_ERROR;
      se.message = "Failed to connected to social-graph-service";
      throw se;
    }
    auto social_graph_client = social_graph_client_wrapper->GetClient();
    std::vector<int64_t> followers_id;
    try {
      social_graph_client->GetFollowers(followers_id, req_id, user_id,
                                        writer_text_map);
    } catch (...) {
      LOG(error) << "Failed to get followers from social-network-service";
      _social_graph_client_pool->Push(social_graph_client_wrapper);
      throw;
    }
    _social_graph_client_pool->Push(social_graph_client_wrapper);

    std::set<int64_t> followers_id_set(followers_id.begin(),
        followers_id.end());
    followers_id_set.insert(user_mentions_id.begin(), user_mentions_id.end());

    // Update Redis ZSet
    auto redis_span = opentracing::Tracer::Global()->StartSpan(
        "RedisUpdate", {opentracing::ChildOf(&span->context())});
    auto redis_client_wrapper = _redis_client_pool->Pop();
    if (!redis_client_wrapper) {
      ServiceException se;
      se.errorCode = ErrorCode::SE_REDIS_ERROR;
      se.message = "Cannot connected to Redis server";
      throw se;
    }
    auto redis_client = redis_client_wrapper->GetClient();
    std::vector<std::string> options{"NX"};
    std::string post_id_str = std::to_string(post_id);
    std::string timestamp_str = std::to_string(timestamp);
    std::multimap<std::string, std::string> value =
        {{timestamp_str, post_id_str}};

    for (auto &follower_id : followers_id_set) {
      redis_client->zadd(std::to_string(follower_id), options, value);
    }

    redis_client->sync_commit();
    redis_span->Finish();
    _redis_client_pool->Push(redis_client_wrapper);
    span->Finish();
  } catch (...) {
    LOG(error) << "OnReveived worker error";
    throw;
  }
}

void HeartbeatSend(AmqpLibeventHandler &handler,
    AMQP::TcpConnection &connection, int interval){
  while(handler.GetIsRunning()){
    LOG(debug) << "Heartbeat sent";
    connection.heartbeat();
    sleep(interval);
  }
}

void WorkerThread(std::string &addr, int port) {
  std::cout << "in WorkerThread" << std::endl;
  std::cout << "addr = " << addr << ", port = " << port << std::endl;

  AmqpLibeventHandler handler;
  AMQP::TcpConnection connection(handler, AMQP::Address(
      addr, port, AMQP::Login("guest", "guest"), "/"));

  std::cout << "After creating connection" << std::endl;

  AMQP::TcpChannel channel(&connection);
  channel.onError(
      [&handler](const char *message) {
        LOG(error) << "Channel error: " << message;
        std::cout << "Channel error: " << message << std::endl;
        handler.Stop();
      });
  channel.declareQueue("write-timeline", AMQP::durable).onSuccess(
      [&connection](const std::string &name, uint32_t messagecount,
                    uint32_t consumercount) {
        LOG(debug) << "Created queue: " << name;
        // std::cout << "Created queue: " << name << std::endl;
      });
  channel.consume("write-timeline", AMQP::noack).onReceived(
      [](const AMQP::Message &msg, uint64_t tag, bool redelivered) {
        LOG(debug) << "Received: " << std::string(msg.body(), msg.bodySize());
        OnReceivedWorker(msg);
      });


  std::thread heartbeat_thread(HeartbeatSend, std::ref(handler),
      std::ref(connection), 30);
  heartbeat_thread.detach();
  handler.Start();
  LOG(debug) << "Closing connection.";
  connection.close();
}

int main(int argc, char *argv[]) {
  signal(SIGINT, sigintHandler);
  init_logger();

  SetUpTracer("config/jaeger-config.yml", "write-home-timeline-service");

  json config_json;
  if (load_config_file("config/service-config.json", &config_json) != 0) {
    exit(EXIT_FAILURE);
  }

  std::cout << "load_config_file done" << std::endl;

  // int port = config_json["write-home-timeline-service"]["port"];

  std::string rabbitmq_addr =
      config_json["write-home-timeline-rabbitmq"]["addr"];
  int rabbitmq_port = config_json["write-home-timeline-rabbitmq"]["port"];

  std::string redis_addr =
      config_json["home-timeline-redis"]["addr"];
  int redis_port = config_json["home-timeline-redis"]["port"];
  int redis_conns = config_json["home-timeline-redis"]["connections"];
  int redis_timeout = config_json["home-timeline-redis"]["timeout_ms"];

  std::string social_graph_service_addr =
      config_json["social-graph-service"]["addr"];
  int social_graph_service_port = config_json["social-graph-service"]["port"];
  int social_graph_service_conns = config_json["social-graph-service"]["connections"];
  int social_graph_service_timeout = config_json["social-graph-service"]["timeout_ms"];

  // ClientPool<RedisClient> redis_client_pool("redis", redis_addr, redis_port,
  //                                           0, 1024, 1000);

  ClientPool<RedisClient> redis_client_pool("redis", redis_addr, redis_port,
                                            0, redis_conns, redis_timeout);

  std::cout << "redis client created" << std::endl;

  // ClientPool<ThriftClient<SocialGraphServiceClient>>
  //     social_graph_client_pool(
  //         "social-graph-service", social_graph_service_addr,
  //         social_graph_service_port, 0, 512, 1000);

  ClientPool<ThriftClient<SocialGraphServiceClient>>
      social_graph_client_pool(
          "social-graph-service", social_graph_service_addr,
          social_graph_service_port, 0, social_graph_service_conns, social_graph_service_timeout);


  std::cout << "social-graph-service client created" << std::endl;

  _redis_client_pool = &redis_client_pool;
  _social_graph_client_pool = &social_graph_client_pool;

  std::unique_ptr<std::thread> threads_ptr[NUM_WORKERS];
  for (auto & thread_ptr : threads_ptr) {
    thread_ptr = std::make_unique<std::thread>(
        WorkerThread, std::ref(rabbitmq_addr), rabbitmq_port);
  }
  for (auto &thread_ptr : threads_ptr) {
    thread_ptr->join();
    if (_teptr) {
      try{
        std::rethrow_exception(_teptr);
      }
      catch(const std::exception &ex)
      {
        LOG(error) << "Thread exited with exception: " << ex.what();
      }
    }
  }



  return 0;
}