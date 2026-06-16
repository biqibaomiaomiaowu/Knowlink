import 'package:flutter/material.dart';

class AppTheme {
  static const Color surface = Color(0xFFE0E5EC);
  static const Color text = Color(0xFF3D4852);
  static const Color ink = text;
  static const Color muted = Color(0xFF6B7280);
  static const Color subtle = Color(0xFF7E8997);
  static const Color accent = Color(0xFF6C63FF);
  static const Color accentLight = Color(0xFF8B84FF);
  static const Color success = Color(0xFF38B2AC);
  static const Color danger = Color(0xFFC45163);
  static const Color line = Color(0xFFD0D7E2);
  static const Color panel = surface;
  static const Color page = surface;

  static const Color brandBlue = accent;
  static const Color brandBlueDark = accentLight;
  static const double radiusCard = 32;
  static const double radiusControl = 16;

  static const List<BoxShadow> raisedShadow = [
    BoxShadow(
      color: Color(0x9EA3B1C6),
      blurRadius: 16,
      offset: Offset(9, 9),
    ),
    BoxShadow(
      color: Color(0x8AFFFFFF),
      blurRadius: 16,
      offset: Offset(-9, -9),
    ),
  ];

  static const List<BoxShadow> smallShadow = [
    BoxShadow(
      color: Color(0x99A3B1C6),
      blurRadius: 10,
      offset: Offset(5, 5),
    ),
    BoxShadow(
      color: Color(0x85FFFFFF),
      blurRadius: 10,
      offset: Offset(-5, -5),
    ),
  ];

  static const List<BoxShadow> insetShadow = [
    BoxShadow(
      color: Color(0x9EA3B1C6),
      blurRadius: 10,
      offset: Offset(6, 6),
      blurStyle: BlurStyle.inner,
    ),
    BoxShadow(
      color: Color(0x85FFFFFF),
      blurRadius: 10,
      offset: Offset(-6, -6),
      blurStyle: BlurStyle.inner,
    ),
  ];

  static ThemeData light() {
    const seed = accent;
    return ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: seed),
      useMaterial3: true,
      splashFactory: InkSparkle.splashFactory,
      scaffoldBackgroundColor: page,
      appBarTheme: const AppBarTheme(centerTitle: false),
      cardTheme: CardThemeData(
        color: panel,
        elevation: 0,
        shadowColor: Colors.transparent,
        surfaceTintColor: panel,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
        ),
      ),
      dividerColor: line,
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: panel,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusControl),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusControl),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusControl),
          borderSide: const BorderSide(color: accent, width: 1.4),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.white,
          minimumSize: const Size(52, 46),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusControl),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ).copyWith(
          elevation: WidgetStateProperty.resolveWith(_buttonElevation),
          shadowColor: WidgetStateProperty.resolveWith(_buttonShadowColor),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: text,
          backgroundColor: surface,
          side: BorderSide.none,
          minimumSize: const Size(52, 44),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusControl),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ).copyWith(
          elevation: WidgetStateProperty.resolveWith(_buttonElevation),
          shadowColor: WidgetStateProperty.resolveWith(_buttonShadowColor),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: text,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusControl),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ).copyWith(
          elevation: WidgetStateProperty.resolveWith(_textButtonElevation),
          shadowColor: WidgetStateProperty.resolveWith(_buttonShadowColor),
        ),
      ),
      textTheme: const TextTheme(
        displaySmall: TextStyle(
          color: ink,
          fontSize: 34,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
        headlineMedium: TextStyle(
          color: ink,
          fontSize: 28,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
        titleLarge: TextStyle(
          color: ink,
          fontSize: 22,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
        titleMedium: TextStyle(
          color: ink,
          fontSize: 18,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
        titleSmall: TextStyle(
          color: ink,
          fontSize: 15,
          fontWeight: FontWeight.w700,
          letterSpacing: 0,
        ),
        bodyMedium: TextStyle(
          color: text,
          fontSize: 14,
          height: 1.45,
          letterSpacing: 0,
        ),
        bodySmall: TextStyle(
          color: muted,
          fontSize: 12,
          height: 1.35,
          letterSpacing: 0,
        ),
      ),
    );
  }

  static double? _buttonElevation(Set<WidgetState> states) {
    if (states.contains(WidgetState.disabled)) {
      return 0;
    }
    if (states.contains(WidgetState.pressed)) {
      return 1;
    }
    if (states.contains(WidgetState.hovered) ||
        states.contains(WidgetState.focused)) {
      return 7;
    }
    return 0;
  }

  static double? _textButtonElevation(Set<WidgetState> states) {
    if (states.contains(WidgetState.hovered) ||
        states.contains(WidgetState.focused)) {
      return 2;
    }
    return 0;
  }

  static Color? _buttonShadowColor(Set<WidgetState> states) {
    if (states.contains(WidgetState.disabled)) {
      return Colors.transparent;
    }
    if (states.contains(WidgetState.hovered) ||
        states.contains(WidgetState.focused)) {
      return accent.withValues(alpha: 0.24);
    }
    return Colors.transparent;
  }
}
