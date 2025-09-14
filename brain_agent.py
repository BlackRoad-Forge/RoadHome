import paho.mqtt.client as mqtt
from langchain_ollama.llms import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langchain import hub
import json
import time

# --- Configuration ---
MQTT_BROKER = "192.168.68.63"
MQTT_PORT = 1883
RESPONSE_TOPIC = "assistant/tts/say"
TRANSCRIPT_TOPIC = "assistant/stt/transcript"
VISION_TOPIC = "assistant/vision/events"
DEVICE_LIST_TOPIC = "assistant/devices/list"

# --- Global State ---
# We use a class to hold state to avoid complex global variables
class AssistantState:
    def __init__(self):
        self.available_devices = []
        self.mqtt_client = None

assistant_state = AssistantState()

# --- Agent Tools ---
# These are the functions the AI agent can choose to run.

@tool
def control_home_assistant_device(entity_id: str, state: str) -> str:
    """
    Controls a Home Assistant device. Use this to turn devices on or off.
    'entity_id' is the unique ID of the device, e.g., 'light.shapes'.
    'state' should be either 'ON' or 'OFF'.
    """
    print(f"TOOL: control_home_assistant_device called with entity_id='{entity_id}', state='{state}'")
    if not assistant_state.mqtt_client:
        return "Error: MQTT client is not available."

    if entity_id not in assistant_state.available_devices:
        return f"Error: Device '{entity_id}' is not in the list of available devices."
    
    domain = entity_id.split('.')[0] # e.g., 'light' or 'switch'
    device_name = entity_id.split('.')[1]
    
    topic = f"homeassistant/{domain}/{device_name}/set"
    payload = state.upper()
    
    assistant_state.mqtt_client.publish(topic, payload)
    return f"Successfully sent command to turn {entity_id} {state}."

@tool
def get_available_devices() -> str:
    """
    Returns a list of all available device entity_ids from Home Assistant.
    """
    print("TOOL: get_available_devices called.")
    if not assistant_state.available_devices:
        return "No devices found. The list might not have been received from Home Assistant yet."
    return f"Available devices: {', '.join(assistant_state.available_devices)}"

# --- LLM and Agent Initialization ---

def initialize_agent():
    print("Brain: Initializing Ollama LLM and Agent...")
    llm = OllamaLLM(model="qwen2.5:3b-instruct-q4_K_M")
    tools = [control_home_assistant_device, get_available_devices]
    
    # Get the ReAct agent prompt from LangChain Hub
    prompt = hub.pull("hwchase17/react")
    
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    print("Brain: Agent Initialized.")
    return agent_executor

# --- MQTT Handlers ---

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Brain: Connected to MQTT Broker!")
        client.subscribe(TRANSCRIPT_TOPIC)
        client.subscribe(VISION_TOPIC)
        client.subscribe(DEVICE_LIST_TOPIC)
    else:
        print(f"Brain: Failed to connect, return code {rc}\n")

def handle_device_list(payload):
    try:
        devices = json.loads(payload)
        assistant_state.available_devices = devices
        print(f"Brain: Updated device list: {assistant_state.available_devices}")
    except json.JSONDecodeError:
        print("Brain: Error decoding device list from Home Assistant.")

def handle_transcript(text, agent_executor):
    print(f"\nBrain: Received Transcript: '{text}'")
    
    if not assistant_state.available_devices:
        response = "I am still starting up and don't have the device list yet. Please try again in a moment."
    else:
        # Let the agent handle the request
        result = agent_executor.invoke({"input": text})
        response = result.get("output", "I'm not sure how to respond to that.")
    
    # Always publish the final answer to the TTS topic
    assistant_state.mqtt_client.publish(RESPONSE_TOPIC, response)
    print(f"Brain: Published response: {response}")

def on_message(client, userdata, msg):
    if msg.topic == DEVICE_LIST_TOPIC:
        handle_device_list(msg.payload.decode())
    elif msg.topic == TRANSCRIPT_TOPIC:
        # We need to pass the agent_executor into the handler
        agent_executor = userdata['agent_executor']
        handle_transcript(msg.payload.decode(), agent_executor)
    # Vision event handling can be added here later

# --- Main Execution ---

def main():
    agent_executor = initialize_agent()
    
    # Store the agent executor in user data to be accessible in on_message
    user_data = {'agent_executor': agent_executor}
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.user_data_set(user_data) # Set user data AFTER client creation
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Give the state object access to the client for the tools
    assistant_state.mqtt_client = client
    
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    print("Brain Agent started...")
    client.loop_forever()

if __name__ == "__main__":
    main()

