# WiFi Messenger App 💬

A local network messaging app built with Streamlit that allows devices on the same WiFi network to chat with each other!

## Features ✨

- 🔍 **Auto-Discovery**: Automatically finds nearby chat rooms on the same network
- 🔐 **6-Digit PIN**: Each chat room has a unique PIN for easy joining
- 💬 **Real-time Messaging**: Instant messaging between connected devices
- 🎯 **Simple Interface**: Easy-to-use Streamlit interface

## How It Works

1. **Create a Chat Room**: One user creates a chat room and gets a 6-digit PIN
2. **Discover Nearby Chats**: Other users can see available chat rooms automatically
3. **Join a Chat**: Click to join or enter the PIN manually
4. **Start Chatting**: Send and receive messages in real-time!

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- All devices must be on the **same WiFi network**

### Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

2. Run the app:
```bash
streamlit run app.py
```

3. The app will open in your browser at `http://localhost:8501`

## Usage Guide

### For the Host (Creating a Chat Room):

1. Enter your username
2. Click "Create Chat Room"
3. Share your **6-digit PIN** and **IP address** with others
4. Wait for others to join and start chatting!

### For Joining Users:

1. Enter your username
2. Wait a few seconds for nearby chats to appear
3. Click "Join" on the chat you want to join
   - OR enter the PIN and IP address manually
4. Start chatting!

## Important Notes

⚠️ **Network Requirements:**
- All devices MUST be on the same WiFi network (same router)
- This will NOT work across different networks or over the internet
- Some corporate/university networks may block this type of communication

⚠️ **Firewall:**
- Your firewall may need to allow Python/Streamlit to access the network
- Ports used: 37020 (discovery) and 37021 (chat)

⚠️ **Running on Multiple Devices:**
- Each device should run its own instance of the app
- Make sure to use different ports if running multiple instances on the same device

## Troubleshooting

**Can't see nearby chats?**
- Make sure all devices are on the same WiFi network
- Check firewall settings
- Try manually entering the PIN and IP address

**Connection failed?**
- Verify the IP address is correct
- Check if the host is still running the app
- Ensure ports 37020 and 37021 aren't blocked

**Messages not sending?**
- Check your internet connection
- Try leaving and rejoining the chat
- Restart the app

## Technical Details

- **Discovery Protocol**: UDP broadcast on port 37020
- **Chat Protocol**: TCP on port 37021
- **Framework**: Streamlit
- **Communication**: Python sockets

## Limitations

- Only works on local network (same WiFi)
- Not encrypted (don't send sensitive information)
- Basic implementation - not production-ready
- Messages are not stored/persisted

## Future Enhancements

- End-to-end encryption
- Message history
- File sharing
- Group chat features
- Better error handling
- User avatars

---

Enjoy chatting! 💬