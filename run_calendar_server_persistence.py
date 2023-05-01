from server import *

# Chat server for persistence. Run after all other chat servers are down.
logname = "other.log"
replica_id, address = REPLICA_IDS[0]
calendar_server = ServerRunner(id=replica_id, address=address)
print("[STARTING] lead server is starting...")
calendar_server.start()

calendar_server.connect_to_replicas(logfile=logname)

calendar_server.wait_for_termination()