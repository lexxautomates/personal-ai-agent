import 'package:flutter/material.dart';

class FloatingGlassView extends StatelessWidget {
  final Widget child;
  const FloatingGlassView({super.key, required this.child});

  @override
  Widget build(BuildContext context) => Container(
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.15),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        padding: const EdgeInsets.all(8),
        child: child,
      );
}

class FloatingGlassButton extends StatelessWidget {
  final IconData sfIcon;
  final Color? iconColor;
  final bool isActive;
  final Widget? subWidget;
  final VoidCallback? onTap;

  const FloatingGlassButton({
    super.key,
    required this.sfIcon,
    this.iconColor,
    this.isActive = false,
    this.subWidget,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) => Material(
        color: isActive ? Colors.white.withValues(alpha: 0.2) : Colors.transparent,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.all(8),
            child: subWidget != null
                ? Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 15,
                        height: 15,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.black.withValues(alpha: 0.4),
                        ),
                        child: subWidget,
                      ),
                      const SizedBox(width: 6),
                      sf.SFIcon(
                        sfIcon,
                        color: iconColor ?? Colors.white,
                        fontSize: 18,
                      ),
                    ],
                  )
                : sf.SFIcon(
                    sfIcon,
                    color: iconColor ?? Colors.white,
                    fontSize: 18,
                  ),
          ),
        ),
      );
}
