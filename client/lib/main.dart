// Personal AI Agent - Flutter companion client
//
// Connects to the same LiveKit agent that powers the voice/call surface,
// and gives the user a phone/laptop app for voice + text interaction with
// the same assistant.
//
// Substrate: lexxautomates/livekit_flutter_starter (fork of livekit/livekit-flutter-starter)
// Backend:   the Python agent in this repo (agent/)
//
// Environment variables (in .env, not committed):
//   LIVEKIT_URL
//   LIVEKIT_API_KEY
//   LIVEKIT_API_SECRET
//   AGENT_ROOM_NAME  (optional - if unset the client joins a fresh room)

import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:livekit_client/livekit_client.dart';

import 'agent_service.dart';
import 'ui/chat_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: '.env');

  runApp(const PersonalAiAgentApp());
}

class PersonalAiAgentApp extends StatelessWidget {
  const PersonalAiAgentApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Personal AI Agent',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const AgentScreen(),
    );
  }
}
