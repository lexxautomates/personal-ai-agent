import 'package:flutter/material.dart';
import 'package:livekit_components/livekit_components.dart' as components;
import 'package:provider/provider.dart';

import '../exts.dart';

class AgentStatusIndicator extends StatelessWidget {
  final bool hideWhenConnected;

  const AgentStatusIndicator({super.key, this.hideWhenConnected = false});

  @override
  Widget build(BuildContext context) => Consumer<components.RoomContext>(
        selector: (context, roomCtx) => roomCtx.agentParticipant?.isConnected ?? false,
        builder: (context, isConnected, child) {
          if (hideWhenConnected && isConnected) {
            return const SizedBox.shrink();
          }
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isConnected ? Colors.greenAccent : Colors.grey,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  isConnected ? 'Agent connected' : 'Agent disconnected',
                  style: const TextStyle(fontSize: 12),
                ),
              ],
            ),
          );
        },
      );
}
