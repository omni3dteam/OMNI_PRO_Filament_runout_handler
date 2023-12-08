# Libraries
import time
import json
# Python dsf API
from dsf.connections import InterceptConnection, InterceptionMode, CommandConnection, BaseCommandConnection
from dsf.commands.code import CodeType
from dsf.object_model import MessageType
from dsf.connections import SubscribeConnection, SubscriptionMode

### Tool number to drive number assigment ###
### Tool 0 <=> 4
### Tool 1 <=> 2
### Tool 2 <=> 5
### Tool 3 <=> 3

class tool_drive:
    tools  = [[0,4],
              [1,2],
              [2,5],
              [3,3]]

    drives = [[2,1],
              [3,3],
              [4,0],
              [5,2]]

    def return_drive_number(self, _tool_number):
        return self.tools[_tool_number][1]

    def return_tool_number(self, _drive_number):
        return self.drives[(_drive_number-2)][1]
    def return_neighbour_tool_number(self, _tool_number):
        if _tool_number > 2:
            return _tool_number - 2
        else:
            return _tool_number + 2

def intercept_data_request():
    filters = ["M1103", "M1104", "M1105", "M1106"]
    intercept_connection = InterceptConnection(InterceptionMode.PRE, filters=filters, debug=False)
    intercept_connection.connect()
    try:
        # Wait for a code to arrive.
        cde = intercept_connection.receive_code()
        intercept_connection.resolve_code(MessageType.Success)
        if cde.type == CodeType.MCode and cde.majorNumber == 1103:
            return 0
        elif cde.type == CodeType.MCode and cde.majorNumber == 1104:
            return 1
        elif cde.type == CodeType.MCode and cde.majorNumber == 1105:
            return 2
        elif cde.type == CodeType.MCode and cde.majorNumber == 1106:
            return 3
        else:
            print("Unsupported MCODE")
    except Exception as e:
        print("Closing connection: ", e)
        intercept_connection.close()

if __name__ == "__main__":
    #Configure everything on entry
    command_connection = CommandConnection(debug=False)
    command_connection.connect()
    while(True):
        # Get extruder with error
        extruder_with_error = intercept_data_request()
        # Pause print
        command_connection.perform_simple_code("M25")
        print(extruder_with_error)
        # Get tool number from extruder drive
        tool = tool_drive().return_tool_number(extruder_with_error)
        # Get state of other tools
        res = command_connection.perform_simple_code("M1102")
        tools_state = [json.loads(res)['Tool_0'], json.loads(res)['Tool_1'], json.loads(res)['Tool_2'], json.loads(res)['Tool_3']]
        # Get neighbouring tool
        neighbour_tool = tool_drive().return_neighbour_tool_number(tool)
        # Check if other tool have valid filament to use
        if tools_state[neighbour_tool] == 1:
            # There is filament present, check RFID info
            # but first get current filament loaded
            # res = command_connection.perform_simple_code("MXXX SX")
            #current_filament = json.dumps(res)["material"]
            print("Checking rfid")
            res = command_connection.perform_simple_code("M1002 S".format(neighbour_tool))
            rfid_info = json.dumps(res)
            if rfid_info["material"] == "ABS-42":
                # We have same filament. We can try to change it.
                # 1. Retract current filament.
                res = command_connection.perform_simple_code("M1102 P{} S2".format(tool))
                # # 2. check if other is loaded. if not load it.
                if tools_state[neighbour_tool] != 2:
                    res = command_connection.perform_simple_code("M1102 P{} S0".format(neighbour_tool))
                # 3. prime extruder.
                res = command_connection.perform_simple_code("M1102 P{} S1".format(neighbour_tool))
                # 4. switch drives.
                if tool == 0 or tool == 2:
                    extruder_drive = 0
                else:
                    extruder_drive = 1
                res = command_connection.perform_simple_code("M563 P{} D{}:{} H1 F1".format(tool, extruder_drive, tool_drive().return_drive_number(neighbour_tool)))
                command_connection.perform_simple_code("M24")
        else:
            # no filament present. Pasue print and send info
            message = """M291 P"Printer run out of filament" R"Filament run-out error" S2"""
            command_connection.perform_simple_code(message)





