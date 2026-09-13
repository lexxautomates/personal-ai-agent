// Agent service - wraps the LiveKit client and owns the connection to the
// personal AI agent.
//
// The client joins a LiveKit room and lets the user send text and, where
// the agent supports it, voice. The same backend Python agent handles
// both the call surface and this client surface.

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:livekit_client/livekit_client.dart';

class AgentService with ChangeNotifier {
  Client? _client;
  Room? _room;
  bool _connected = false;
  String? _error;

  bool get connected => _connected;
  String? get error => _error;

  /// Connect to the personal AI agent's LiveKit room.
  Future<void> connect() async {
    _error = null;
    notifyListeners();

    final url = dotenv.env['LIVEKIT_URL'] ?? '';
    final apiKey = dotenv.env['LIVEKIT_API_KEY'] ?? '';
    final apiSecret = dotenv.env['LIVEKIT_API_SECRET'] ?? '';
    final roomName =
        dotenv.env['AGENT_ROOM_NAME'] ?? 'personal-ai-agent-room';

    if (url.isEmpty || apiKey.isEmpty || apiSecret.isEmpty) {
      _error = 'LiveKit credentials not configured in .env';
      notifyListeners();
      return;
    }

    try {
      _client = await Client.connect(
        url,
        token: TwilioToken(
          apiKey,
          apiSecret,
          identity: 'personal-ai-client',
          roomName: roomName,
          expirySeconds: 3600,
        ),
      );

      _room = await _client!.room(
        roomName,
        roomOptions: RoomOptions(
          roomName: roomName,
          publishDefaults: RoomPublishOptions(
            videoCodec: VideoCodec.h264,
            audioCodec: AudioCodec.opus,
          ),
        ),
      );

      _room!.on(RoomEvent.forgotten, (_) {
        _connected = false;
        notifyListeners();
      });
      _room!.on(RoomEvent.disconnected, (_) {
        _connected = false;
        notifyListeners();
      });

      _connected = true;
      notifyListeners();
    } catch (e) {
      _error = 'Failed to connect to the agent: $e';
      notifyListeners();
    }
  }

  /// Disconnect from the agent room.
  Future<void> disconnect() async {
    await _room?.disconnect();
    await _client?.disconnect();
    _room = null;
    _client = null;
    _connected = false;
    notifyListeners();
  }

  /// Send a text message to the agent.
  void sendText(String text) {
    if (_room == null || !_connected) return;
    // The LiveKit agent receives this as a text participant message.
    // The backend agent is the same one that handles the voice call surface.
    _room!.sendData(
      Uint8List.fromList(utf8.encode(text)),
      dataAttributes: {'type': 'text', 'message': text},
    );
  }
}
