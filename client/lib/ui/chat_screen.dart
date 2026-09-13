// Chat / voice screen - the main interaction surface for the personal AI agent.
//
// Voice and text both reach the same backend Python agent. Voice uses the
// LiveKit mic/call path; text uses the data channel in agent_service.dart.

import 'package:flutter/material.dart';
import 'package:chat_bubbles/chat_bubbles.dart';
import '../agent_service.dart';

class AgentScreen extends StatefulWidget {
  const AgentScreen({super.key});

  @override
  State<AgentScreen> createState() => _AgentScreenState();
}

class _AgentScreenState extends State<AgentScreen> {
  final _agentService = AgentService();
  final _messageController = TextEditingController();
  final _messages = <ChatMessage>[];

  @override
  void initState() {
    super.initState();
    _agentService.addListener(_onAgentChanged);
    _agentService.connect();
  }

  @override
  void dispose() {
    _agentService.removeListener(_onAgentChanged);
    _agentService.dispose();
    _messageController.dispose();
    super.dispose();
  }

  void _onAgentChanged() {
    // React to connection state changes if needed.
    setState(() {});
  }

  void _sendText() {
    final text = _messageController.text.trim();
    if (text.isEmpty || !_agentService.connected) return;

    setState(() {
      _messages.add(ChatMessage.sender(text: text));
      _messageController.clear();
    });

    _agentService.sendText(text);

    // The agent's reply comes back through the LiveKit data channel or
    // voice path; in a fuller client that reply would be rendered here.
    setState(() {
      _messages.add(ChatMessage.receiver(text: '...'));
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Personal AI Agent'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _agentService.connect(),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? const Center(child: Text('Connecting to your assistant...'))
                : ListView.builder(
                    reverse: true,
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      final msg = _messages[index];
                      return Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 4,
                        ),
                        child: msg.isSender
                            ? Bubble(
                                child: Text(msg.text),
                                color: Colors.deepPurple.withOpacity(0.2),
                              )
                            : Bubble(
                                child: Text(msg.text),
                                color: Colors.grey.withOpacity(0.2),
                                alignment: Alignment.centerLeft,
                              ),
                      );
                    },
                  ),
          ),
          _agentService.connected
              ? Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _messageController,
                          decoration: const InputDecoration(
                            hintText: 'Type a message...',
                            border: OutlineInputBorder(),
                          ),
                          onSubmitted: (_) => _sendText(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        icon: const Icon(Icons.send),
                        onPressed: _sendText,
                      ),
                    ],
                  ),
                )
              : const Padding(
                  padding: EdgeInsets.all(8.0),
                  child: Row(
                    children: [
                      CircularProgressIndicator(),
                      SizedBox(width: 8),
                      Text('Connecting...'),
                    ],
                  ),
                ),
        ],
      ),
    );
  }
}

class ChatMessage {
  final String text;
  final bool isSender;
  const ChatMessage({required this.text, required this.isSender});
  factory ChatMessage.sender({required String text}) =>
      ChatMessage(text: text, isSender: true);
  factory ChatMessage.receiver({required String text}) =>
      ChatMessage(text: text, isSender: false);
}
