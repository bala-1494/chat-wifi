import streamlit as st
import socket
import threading
import json
import time
import random
import string
from datetime import datetime
from queue import Queue

# Page config
st.set_page_config(page_title="WiFi Messenger", page_icon="💬", layout="wide")

# Initialize session state
if 'username' not in st.session_state:
    st.session_state.username = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'chat_socket' not in st.session_state:
    st.session_state.chat_socket = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'chat_id' not in st.session_state:
    st.session_state.chat_id = None
if 'is_host' not in st.session_state:
    st.session_state.is_host = False
if 'server_thread' not in st.session_state:
    st.session_state.server_thread = None
if 'nearby_chats' not in st.session_state:
    st.session_state.nearby_chats = []
if 'stop_threads' not in st.session_state:
    st.session_state.stop_threads = threading.Event()
if 'message_queue' not in st.session_state:
    st.session_state.message_queue = Queue()
if 'broadcast_thread' not in st.session_state:
    st.session_state.broadcast_thread = None
if 'discovery_thread' not in st.session_state:
    st.session_state.discovery_thread = None

# Constants
BROADCAST_PORT = 37020
CHAT_PORT = 37021
DISCOVERY_MESSAGE = "WIFI_MESSENGER_DISCOVERY"

def generate_chat_id():
    """Generate a random 6-digit PIN"""
    return ''.join(random.choices(string.digits, k=6))

def get_local_ip():
    """Get the local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def broadcast_presence(chat_id, username, stop_event):
    """Broadcast presence on the network"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    message = json.dumps({
        'type': 'presence',
        'chat_id': chat_id,
        'username': username,
        'ip': get_local_ip(),
        'timestamp': time.time()
    })
    
    while not stop_event.is_set():
        try:
            sock.sendto(message.encode(), ('<broadcast>', BROADCAST_PORT))
            time.sleep(2)
        except:
            break
    sock.close()

def listen_for_broadcasts(nearby_chats_list, stop_event):
    """Listen for nearby chat rooms"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', BROADCAST_PORT))
    sock.settimeout(1.0)
    
    while not stop_event.is_set():
        try:
            data, addr = sock.recvfrom(1024)
            message = json.loads(data.decode())
            
            if message['type'] == 'presence':
                # Update nearby chats
                chat_info = {
                    'chat_id': message['chat_id'],
                    'username': message['username'],
                    'ip': message['ip'],
                    'last_seen': time.time()
                }
                
                # Remove old entries and update
                nearby_chats_list[:] = [
                    chat for chat in nearby_chats_list 
                    if chat['chat_id'] != message['chat_id']
                ]
                nearby_chats_list.append(chat_info)
                
                # Remove chats not seen in 10 seconds
                current_time = time.time()
                nearby_chats_list[:] = [
                    chat for chat in nearby_chats_list
                    if current_time - chat['last_seen'] < 10
                ]
        except socket.timeout:
            continue
        except:
            break
    sock.close()

def start_chat_server(chat_id, stop_event, message_queue):
    """Start server to accept incoming connections"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', CHAT_PORT))
    server.listen(5)
    server.settimeout(1.0)
    
    clients = []
    
    def broadcast_to_clients(message_data):
        """Send message to all connected clients"""
        dead_clients = []
        for client in clients:
            try:
                client.send(json.dumps(message_data).encode())
            except:
                dead_clients.append(client)
        
        # Remove dead clients
        for client in dead_clients:
            clients.remove(client)
            try:
                client.close()
            except:
                pass
    
    while not stop_event.is_set():
        try:
            # Accept new connections
            client_socket, address = server.accept()
            clients.append(client_socket)
            threading.Thread(target=handle_client, args=(client_socket, message_queue), daemon=True).start()
        except socket.timeout:
            pass
        except:
            break
        
        # Check for messages to broadcast
        while not message_queue.empty():
            try:
                message = message_queue.get_nowait()
                broadcast_to_clients(message)
            except:
                break
    
    # Cleanup
    for client in clients:
        try:
            client.close()
        except:
            pass
    server.close()

def handle_client(client_socket, message_queue):
    """Handle messages from a connected client"""
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            
            message = json.loads(data.decode())
            message_queue.put(message)
    except:
        pass
    finally:
        client_socket.close()

def connect_to_chat(ip, chat_id, message_queue):
    """Connect to an existing chat"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, CHAT_PORT))
        st.session_state.chat_socket = sock
        st.session_state.connected = True
        st.session_state.chat_id = chat_id
        
        # Start listening thread
        threading.Thread(target=receive_messages, args=(sock, message_queue), daemon=True).start()
        return True
    except Exception as e:
        st.error(f"Failed to connect: {e}")
        return False

def receive_messages(sock, message_queue):
    """Receive messages from server"""
    try:
        while True:
            data = sock.recv(1024)
            if not data:
                break
            
            message = json.loads(data.decode())
            message_queue.put(message)
    except:
        pass

def send_message(text):
    """Send a message"""
    message = {
        'username': st.session_state.username,
        'text': text,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    }
    
    if st.session_state.is_host:
        # Host: add to local messages and broadcast to clients
        st.session_state.messages.append(message)
        st.session_state.message_queue.put(message)
    else:
        # Client: send to server
        try:
            st.session_state.chat_socket.send(json.dumps(message).encode())
            # Also add to local messages for immediate display
            st.session_state.messages.append(message)
        except:
            st.error("Failed to send message")

# UI
st.title("💬 WiFi Messenger")

# Username setup
if not st.session_state.username:
    st.subheader("Welcome! Choose a username")
    username = st.text_input("Username", max_chars=20)
    if st.button("Continue") and username:
        st.session_state.username = username
        # Start broadcast listener
        if st.session_state.discovery_thread is None or not st.session_state.discovery_thread.is_alive():
            st.session_state.discovery_thread = threading.Thread(
                target=listen_for_broadcasts, 
                args=(st.session_state.nearby_chats, st.session_state.stop_threads),
                daemon=True
            )
            st.session_state.discovery_thread.start()
        st.rerun()

elif not st.session_state.connected:
    st.write(f"👤 Logged in as: **{st.session_state.username}**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔵 Create New Chat")
        if st.button("Create Chat Room", use_container_width=True):
            chat_id = generate_chat_id()
            st.session_state.chat_id = chat_id
            st.session_state.is_host = True
            st.session_state.connected = True
            st.session_state.stop_threads.clear()
            
            # Start server
            threading.Thread(
                target=start_chat_server, 
                args=(chat_id, st.session_state.stop_threads, st.session_state.message_queue), 
                daemon=True
            ).start()
            # Start broadcasting
            st.session_state.broadcast_thread = threading.Thread(
                target=broadcast_presence, 
                args=(chat_id, st.session_state.username, st.session_state.stop_threads), 
                daemon=True
            )
            st.session_state.broadcast_thread.start()
            
            st.rerun()
    
    with col2:
        st.subheader("🟢 Join Existing Chat")
        
        # Show nearby chats
        if st.session_state.nearby_chats:
            st.write("**Nearby Chats:**")
            for chat in st.session_state.nearby_chats:
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.write(f"📱 {chat['username']}'s chat (PIN: {chat['chat_id']})")
                with col_b:
                    if st.button("Join", key=f"join_{chat['chat_id']}"):
                        if connect_to_chat(chat['ip'], chat['chat_id'], st.session_state.message_queue):
                            st.rerun()
        else:
            st.info("Scanning for nearby chats... Make sure someone has created a chat room on the same network.")
        
        # Manual join option
        st.write("**Or enter PIN manually:**")
        manual_pin = st.text_input("6-Digit PIN", max_chars=6)
        manual_ip = st.text_input("Host IP Address")
        if st.button("Connect") and manual_pin and manual_ip:
            if connect_to_chat(manual_ip, manual_pin, st.session_state.message_queue):
                st.rerun()

else:
    # Chat interface
    st.write(f"👤 **{st.session_state.username}** | 📱 Chat ID: **{st.session_state.chat_id}** | 🌐 IP: **{get_local_ip()}**")
    
    if st.button("🚪 Leave Chat"):
        st.session_state.connected = False
        st.session_state.stop_threads.set()
        st.session_state.chat_id = None
        st.session_state.is_host = False
        if st.session_state.chat_socket:
            try:
                st.session_state.chat_socket.close()
            except:
                pass
            st.session_state.chat_socket = None
        st.session_state.messages = []
        st.session_state.message_queue = Queue()
        st.session_state.stop_threads = threading.Event()
        st.rerun()
    
    # Process incoming messages from queue
    while not st.session_state.message_queue.empty():
        try:
            message = st.session_state.message_queue.get_nowait()
            # Only add if not already in messages (avoid duplicates for host)
            if not any(m.get('timestamp') == message.get('timestamp') and 
                      m.get('username') == message.get('username') and 
                      m.get('text') == message.get('text') 
                      for m in st.session_state.messages):
                st.session_state.messages.append(message)
        except:
            break
    
    st.divider()
    
    # Messages display
    message_container = st.container(height=400)
    with message_container:
        for msg in st.session_state.messages:
            if msg['username'] == st.session_state.username:
                st.markdown(f"**You** ({msg['timestamp']}): {msg['text']}")
            else:
                st.markdown(f"**{msg['username']}** ({msg['timestamp']}): {msg['text']}")
    
    # Message input
    with st.form(key='message_form', clear_on_submit=True):
        col1, col2 = st.columns([5, 1])
        with col1:
            message_text = st.text_input("Message", label_visibility="collapsed", placeholder="Type your message...")
        with col2:
            send_button = st.form_submit_button("Send", use_container_width=True)
        
        if send_button and message_text:
            send_message(message_text)
            st.rerun()
    
    # Auto-refresh to show new messages
    time.sleep(0.5)
    st.rerun()