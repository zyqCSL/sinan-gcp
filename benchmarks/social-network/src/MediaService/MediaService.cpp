#include <signal.h>

#include <thrift/server/TThreadedServer.h>
#include <thrift/protocol/TBinaryProtocol.h>
#include <thrift/transport/TServerSocket.h>
#include <thrift/transport/TBufferTransports.h>

#include "../utils.h"
#include "MediaHandler.h"

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
  SetUpTracer("config/jaeger-config.yml", "media-service");
  json config_json;
  if (load_config_file("config/service-config.json", &config_json) != 0) {
    exit(EXIT_FAILURE);
  }

  int port = config_json["media-service"]["port"];
  const std::string compose_addr = config_json["compose-post-service"]["addr"];
  int compose_port = config_json["compose-post-service"]["port"];
  int compose_conns = config_json["compose-post-service"]["connections"];
  int compose_timeout = config_json["compose-post-service"]["timeout_ms"];

  ClientPool<ThriftClient<ComposePostServiceClient>> compose_post_client_pool(
      "compose-post", compose_addr, compose_port, 0, compose_conns, compose_timeout);

  TThreadedServer server (
      std::make_shared<MediaServiceProcessor>(
          std::make_shared<MediaHandler>(
              &compose_post_client_pool)),
      std::make_shared<TServerSocket>("0.0.0.0", port),
      std::make_shared<TFramedTransportFactory>(),
      std::make_shared<TBinaryProtocolFactory>()
  );

  std::cout << "Starting the media-service server..." << std::endl;
  server.serve();
}
