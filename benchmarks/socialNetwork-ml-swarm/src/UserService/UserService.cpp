#include <thrift/protocol/TBinaryProtocol.h>
#include <thrift/server/TThreadedServer.h>
#include <thrift/transport/TServerSocket.h>
#include <thrift/transport/TBufferTransports.h>
#include <signal.h>


#include "../utils.h"
#include "../utils_memcached.h"
#include "../utils_mongodb.h"
#include "UserHandler.h"

using apache::thrift::server::TThreadedServer;
using apache::thrift::transport::TServerSocket;
using apache::thrift::transport::TFramedTransportFactory;
using apache::thrift::protocol::TBinaryProtocolFactory;
using namespace social_network;

void sigintHandler(int sig) {
  exit(EXIT_SUCCESS);
}

int main(int argc, char *argv[]) {
  signal(SIGINT, sigintHandler);
  init_logger();

  SetUpTracer("config/jaeger-config.yml", "user-service");

  json config_json;
  if (load_config_file("config/service-config.json", &config_json) != 0) {
    exit(EXIT_FAILURE);
  }

  std::string secret = config_json["secret"];

  int port = config_json["user-service"]["port"];
  std::string compose_post_addr = config_json["compose-post-service"]["addr"];
  int compose_post_port = config_json["compose-post-service"]["port"];
  int compose_post_conns = config_json["compose-post-service"]["connections"];
  int compose_post_timeout = config_json["compose-post-service"]["timeout_ms"];

  std::string social_graph_addr = config_json["social-graph-service"]["addr"];
  int social_graph_port = config_json["social-graph-service"]["port"];
  int social_graph_conns = config_json["social-graph-service"]["connections"];
  int social_graph_timeout = config_json["social-graph-service"]["timeout_ms"];

  int mongodb_conns = config_json["user-mongodb"]["connections"];
  int mongodb_timeout = config_json["user-mongodb"]["timeout_ms"];

  int memcached_conns = config_json["user-memcached"]["connections"];
  int memcached_timeout = config_json["user-memcached"]["timeout_ms"];

  memcached_pool_st *memcached_client_pool =
      init_memcached_client_pool(config_json, "user", 32, memcached_conns);
  mongoc_client_pool_t *mongodb_client_pool =
      init_mongodb_client_pool(config_json, "user", mongodb_conns);

  if (memcached_client_pool == nullptr || mongodb_client_pool == nullptr) {
    return EXIT_FAILURE;
  }

  std::string machine_id;
  if (GetMachineId(&machine_id) != 0) {
    exit(EXIT_FAILURE);
  }

  std::mutex thread_lock;

  ClientPool<ThriftClient<ComposePostServiceClient>> compose_post_client_pool(
      "compose-post", compose_post_addr, compose_post_port, 0, compose_post_conns, compose_post_timeout);

  ClientPool<ThriftClient<SocialGraphServiceClient>> social_graph_client_pool(
      "social-graph", social_graph_addr, social_graph_port, 0, social_graph_conns, social_graph_timeout);

  mongoc_client_t *mongodb_client = mongoc_client_pool_pop(mongodb_client_pool);
  if (!mongodb_client) {
    LOG(fatal) << "Failed to pop mongoc client";
    return EXIT_FAILURE;
  }
  bool r = false;
  while (!r) {
    r = CreateIndex(mongodb_client, "user", "user_id", true);
    if (!r) {
      LOG(error) << "Failed to create mongodb index, try again";
      sleep(1);
    }
  }
  mongoc_client_pool_push(mongodb_client_pool, mongodb_client);

  TThreadedServer server(
      std::make_shared<UserServiceProcessor>(
          std::make_shared<UserHandler>(
              &thread_lock,
              machine_id,
              secret,
              memcached_client_pool,
              mongodb_client_pool,
              &compose_post_client_pool,
              &social_graph_client_pool)),
      std::make_shared<TServerSocket>("0.0.0.0", port),
      std::make_shared<TFramedTransportFactory>(),
      std::make_shared<TBinaryProtocolFactory>()
  );
  std::cout << "Starting the user-service server ..." << std::endl;
  server.serve();
}