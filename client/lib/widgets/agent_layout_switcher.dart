import 'package:flutter/material.dart';
import 'package:livekit_components/livekit_components.dart' as components;
import 'package:provider/provider.dart';

import '../controllers/app_ctrl.dart';

class AgentLayoutSwitcher extends StatelessWidget {
  final AgentLayoutState layoutState;
  final Widget Function(BuildContext context) buildAgentView;
  final Widget Function(BuildContext context) buildCameraView;
  final Widget Function(BuildContext context) buildScreenShareView;
  final Widget Function(BuildContext context) transcriptionsBuilder;

  const AgentLayoutSwitcher({
    super.key,
    required this.layoutState,
    required this.buildAgentView,
    required this.buildCameraView,
    required this.buildScreenShareView,
    required this.transcriptionsBuilder,
  });

  @override
  Widget build(BuildContext context) => Stack(
        children: [
          Positioned.fill(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              child: layoutState.isCameraVisible
                  ? buildCameraView(context)
                  : layoutState.isScreenshareVisible
                      ? buildScreenShareView(context)
                      : buildAgentView(context),
            ),
          ),
        ],
      );
}

class AgentLayoutState {
  final bool isTranscriptionVisible;
  final bool isCameraVisible;
  final bool isScreenshareVisible;

  const AgentLayoutState({
    required this.isTranscriptionVisible,
    required this.isCameraVisible,
    required this.isScreenshareVisible,
  });
}
