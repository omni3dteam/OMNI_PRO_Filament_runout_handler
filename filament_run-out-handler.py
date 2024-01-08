# Libraries
import time
import json
from threading import Thread
import queue
# Python dsf API
from dsf.connections import InterceptConnection, InterceptionMode, CommandConnection
from dsf.commands.code import CodeType
from dsf.object_model import MessageType

# Global variables
filament_runout_queue = queue.Queue()
return_to_default_tools = False
# Object used to represent relation between tool number and drive number.
class tool_drive:
    tools  = [[0,2],
              [1,4],
              [2,3],
              [3,5]]

    drives = [[2,1],
              [3,3],
              [4,0],
              [5,2]]

    def return_drive_number(self, _tool_number):
        return self.tools[_tool_number][1]

    def return_tool_number(self, _drive_number):
        return self.drives[(_drive_number-2)][1]

    def return_neighbour_tool_number(self, _tool_number):
        if _tool_number >= 2:
            return _tool_number - 2
        else:
            return _tool_number + 2

def intercept_data_request():
    filters = ["M1103", "M1104", "M1105", "M1106"]
    intercept_connection = InterceptConnection(InterceptionMode.PRE, filters=filters, debug=False)
    intercept_connection.connect()
    while(True):
        try:
            # Wait for a code to arrive.
            cde = intercept_connection.receive_code()
            intercept_connection.resolve_code(MessageType.Success)
            if cde.type == CodeType.MCode and cde.majorNumber == 1103:
                filament_runout_queue.put(3)
                return 3
            elif cde.type == CodeType.MCode and cde.majorNumber == 1104:
                filament_runout_queue.put(1)
                return 1
            elif cde.type == CodeType.MCode and cde.majorNumber == 1105:
                filament_runout_queue.put(2)
                return 2
            elif cde.type == CodeType.MCode and cde.majorNumber == 1106:
                filament_runout_queue.put(0)
                return 0
            else:
                print("Unsupported MCODE")
        except Exception as e:
            print("Closing connection: ", e)
            intercept_connection.close()

# filament_runout_intercept_thread = Thread(target=intercept_data_request).start()

if __name__ == "__main__":
    #Configure everything on entry`
    command_connection = CommandConnection(debug=False)
    command_connection.connect()
    while(True):
    # Get extruder with error
    # if not filament_runout_queue.empty():
        # tool_with_error = filament_runout_queue.get()
        tool = intercept_data_request()
        state = json.loads(command_connection.perform_simple_code("""M409 K"'state.status"'"""))["result"]
        # TODO Check if current tool is the same as error tool
        if state == "processing":
            # Pause print
            command_connection.perform_simple_code("M25")
            print(tool)
            # Get tool number from extruder drive
            # tool = tool_drive().return_tool_number(tool_with_error)
            # Get state of other tools
            res = command_connection.perform_simple_code("M1102")
            tools_state = [json.loads(res)['Tool_0'], json.loads(res)['Tool_1'], json.loads(res)['Tool_2'], json.loads(res)['Tool_3']]
            # Get neighbouring tool
            neighbour_tool = tool_drive().return_neighbour_tool_number(tool)
            # Check if other tool have valid filament to use
            if tools_state[neighbour_tool] == 2:
                # There is filament present, check RFID info
                # but first get current filament loaded
                # res = command_connection.perform_simple_code("MXXX SX")
                # current_filament = json.dumps(res)["material"]
                # print("Checking rfid")
                # res = command_connection.perform_simple_code("M1002 S".format(neighbour_tool))
                # rfid_info = json.dumps(res)
                # if rfid_info["material"] == "ABS-42":
                # We have same filament. We can try to change it.
                # 0. reset to default
                res = command_connection.perform_simple_code("""M98 P"'/sys/configure-tools.g"'""")
                # time.sleep(0.5)
                # 1. Retract current filament.
                res = command_connection.perform_simple_code("M1101 P{} S2".format(tool))
                while tools_state[tool] == 3:
                    res = command_connection.perform_simple_code("M1102")
                    tools_state = [json.loads(res)['Tool_0'], json.loads(res)['Tool_1'], json.loads(res)['Tool_2'], json.loads(res)['Tool_3']]
                    time.sleep(0.7)
                # 2. check if other is loaded. if not load it.
                if tools_state[neighbour_tool] != 2:
                    res = command_connection.perform_simple_code("M1101 P{} S0".format(neighbour_tool))
                    time.sleep(1)
                # 3. prime extruder.
                # time.sleep(1)
                res = command_connection.perform_simple_code("M1101 P{} S1".format(neighbour_tool))
                while tools_state[neighbour_tool] != 3:
                    res = command_connection.perform_simple_code("M1102")
                    tools_state = [json.loads(res)['Tool_0'], json.loads(res)['Tool_1'], json.loads(res)['Tool_2'], json.loads(res)['Tool_3']]
                    time.sleep(0.7)
                #5. switch drives.
                heater = 0
                if tool == 0 or tool == 2:
                    extruder_drive = 0
                    heater = 0
                else:
                    extruder_drive = 1
                    heater = 1
                res = command_connection.perform_simple_code("M563 P{}".format(extruder_drive))
                # time.sleep(0.5)
                message = "M563 P{} D{}:{} H{} F{}".format(tool, extruder_drive, tool_drive().return_drive_number(neighbour_tool), heater, heater)
                res = command_connection.perform_simple_code(message)
                # time.sleep(0.5)
                res = command_connection.perform_simple_code("G10 P{} X0 Y0 Z0".format(tool))
                # time.sleep(0.5)
                # TODO fix default temperature change and other temperature things.
                res = command_connection.perform_simple_code("G10 P{} R250 S250".format(tool))
                # time.sleep(0.5)
                res = command_connection.perform_simple_code("M567 P{} E1.0:1.05".format(tool))
                # TODO get back to default config at the end of print.
                # res = command_connection.perform_simple_code("G92 U0 V0 W0 A0")
                # time.sleep(0.5)
                res = command_connection.perform_simple_code("G92 E0 U0 V0 W0 A0")
                # 4. Select tool
                command_connection.perform_simple_code("T{}".format(tool))
                # time.sleep(0.5)
                command_connection.perform_simple_code("M24")
            else:
                # no filament present. Pasue print and send info
                message = """M291 P"Printer run out of filament" R"Filament run-out error" S2"""
                command_connection.perform_simple_code(message)
        # else:
        #     state = json.loads(command_connection.perform_simple_code("""M409 K"'state.status"'"""))["result"]
        #     if state == "processing":
        #         return_to_default_tools = True
        #     if state == "idle" and return_to_default_tools:
        #          res = command_connection.perform_simple_code("""M98 P"/sys/configure-tools.g""")
        #          time.sleep(0.5)
        #          return_to_default_tools = False
        #     time.sleep(1)








