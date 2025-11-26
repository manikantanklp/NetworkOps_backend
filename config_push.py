from netmiko import ConnectHandler

def push_config(ip, username, password, commands):
    try:
        conn = ConnectHandler(
            device_type="cisco_ios",
            host=ip,
            username=username,
            password=password
        )
        conn.enable()
        output = conn.send_config_set(commands)
        conn.disconnect()
        return {"status": "success", "output": output}

    except Exception as e:
        return {"status": "error", "error": str(e)}
