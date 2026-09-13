import 'package:flutter/material.dart';
import 'package:flutter_sficon/flutter_sficon.dart' as sf;
import 'package:livekit_components/livekit_components.dart' as components;
import 'package:provider/provider.dart';

import '../app.dart';
import '../controllers/app_ctrl.dart' show AppCtrl, AgentScreenState;
import '../ui/color_pallette.dart' show LKColorPaletteLight;
import 'floating_glass.dart';

class CameraToggleButton extends StatelessWidget {
  final VoidCallback onTap;

  const CameraToggleButton({super.key, required this.onTap});

  @override
  Widget build(BuildContext context) => FloatingGlassButton(
        sfIcon: sf.SFIcons.sf_video_fill,
        onTap: onTap,
      );
}
