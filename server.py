from opcua import Server
import random
import time

server = Server()
server.set_endpoint("opc.tcp://0.0.0.0:4840")
server.set_server_name("PLC Simulator")

idx = server.register_namespace("PLC")
objects = server.get_objects_node()
plc = objects.add_object(idx, "PLC")

# Параметры
params = [
    ("Temperature", 25.0),
    ("Pressure", 100.0),
    ("Humidity", 50.0),
    ("Vibration", 1.0),
    ("Current", 2.0),
    ("Speed", 1000.0),
    ("Level", 50.0),
    ("Frequency", 50.0)
]

variables = {}
for name, default in params:
    var = plc.add_variable(idx, name, default)
    var.set_writable(True)
    variables[name] = var

server.start()
print("✅ OPC UA сервер запущен на opc.tcp://0.0.0.0:4840")
print("Эмулируем параметры:", [name for name, _ in params])

try:
    while True:
        for name, var in variables.items():
            if name == "Temperature":
                val = 20.0 + random.random() * 10.0
            elif name == "Pressure":
                val = 90.0 + random.random() * 20.0
            elif name == "Humidity":
                val = 40.0 + random.random() * 40.0
            elif name == "Vibration":
                val = 0.5 + random.random() * 5.0
            elif name == "Current":
                val = 1.0 + random.random() * 8.0
            elif name == "Speed":
                val = 800.0 + random.random() * 800.0
            elif name == "Level":
                val = 10.0 + random.random() * 80.0
            elif name == "Frequency":
                val = 45.0 + random.random() * 10.0
            else:
                val = 0.0
            var.set_value(round(val, 2))
        time.sleep(2)
except KeyboardInterrupt:
    print("Остановка сервера")
finally:
    server.stop()