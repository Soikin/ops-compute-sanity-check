#!/usr/bin/env python
import openstack
import sys
import os
import time

# openstack.enable_logging(debug=True)

build_number = sys.argv[1]
cloud_name = sys.argv[2]
compute_node = sys.argv[3]
destination_node = sys.argv[4:]

server_name = "test-jenkins-build-" + build_number

network = "int_network"
image = "Cirros"
flavor = "m1.tiny"
new_flavor = "cpu_2.ram_1"
floating_network = "badbb152-5def-4285-a947-5b09750525d8"

def aggregate_check(conn):
  aggregate = False
  for aggr in conn.list_aggregates():
    if compute_node in aggr.hosts:
      print("Compute node " + compute_node + " is in " + aggr.name + " aggregate.")
      aggregate = True
  if not aggregate:
    print("Compute node " + compute_node + " not included of any aggregate.")

def delete_server(conn, server):
  if server:
    print("Deleting server...")
    conn.compute.delete_server(server)
  else:
    print("Failed to delete server. Server not found.")
    sys.exit(30)

def get_az(conn, node):
  for az in conn.compute.availability_zones(details=True):
    if node in az.hosts:
      return az.name + ":" + node

def create_server(conn):
  if conn.compute.find_server(server_name):
    print("There is already an existing VM with name '" + server_name + "'.")
    sys.exit(25)
  else:
    img = conn.compute.find_image(image)
    fv = conn.compute.find_flavor(flavor)
    net = conn.network.find_network(network)
    az = get_az(conn, compute_node)

    print("Creating server...")
    server = conn.compute.create_server(name=server_name, image_id=img.id, flavor_id=fv.id, networks=[{"uuid": net.id}], availability_zone=az)
    floating_ip = conn.available_floating_ip(floating_network).floating_ip_address
    conn.compute.wait_for_server(server)
    conn.compute.add_floating_ip_to_server(server, floating_ip)
    conn.compute.wait_for_server(server)
    server = conn.compute.get_server(server)
    print("Server created with name " + server.name + " and public ip " + floating_ip)
    return server, floating_ip

def ping(conn, server, floating_ip):
  print("Trying ping " + floating_ip + "...")
  time.sleep(5)
  if os.system("ping -c 1 " + floating_ip + " > /dev/null 2>&1"):
    print(floating_ip + " isn't pinging. =(")
    delete_server(conn, server)
    sys.exit(20)
  else:
    print(floating_ip + " is pinging. =)")

def migrate_server(conn, server, node):
  print("Trying migrate server to " + node + "...")
  conn.compute.live_migrate_server(server=server, host=node, force=True, block_migration=None)

def resize_server(conn, server):
  print("Trying resize server " + server_name + "...")
  conn.compute.resize_server(server, conn.compute.find_flavor(new_flavor))
  for i in range(20):
    vm_state = conn.compute.get_server(server).vm_state
    if vm_state != "resized":
      print("VM state: " + vm_state)
      time.sleep(5)
      if i == 10:
        print("Error. Resizing timeout. =(")
        delete_server(conn, server)
        sys.exit(5)
    else:
      print("VM state: " + vm_state + ". Confirming...")
      conn.compute.confirm_server_resize(server)
      print("Server " + server_name + " successfully resized! =)")
      break

def main():
  conn = openstack.connect(cloud_name)
  aggregate_check(conn)
  server, floating_ip = create_server(conn)
  ping(conn, server, floating_ip)
  # migrate_server(conn, server, destination_node)
  resize_server(conn, server)
  ping(conn, server, floating_ip)
  delete_server(conn, server)

if __name__ == '__main__':
  start = time.time()
  main()
  print "It took", time.time()-start, "seconds."
