import 'package:flutter/material.dart';

class AppTheme {
  static const Color surface = Color(0xFFE0E5EC);
  static const Color brandBlue = Color(0xFF6C63FF);
  static const Color brandBlueDark = Color(0xFF544CD2);
  static const Color accentLight = Color(0xFF8B84FF);
  static const Color success = Color(0xFF38B2AC);
  static const Color danger = Color(0xFFC45163);
  static const Color ink = Color(0xFF3D4852);
  static const Color muted = Color(0xFF6B7280);
  static const Color subtle = Color(0xFF7E8997);
  static const Color line = Color(0x00000000);
  static const Color panel = surface;
  static const Color page = surface;

  static const List<BoxShadow> shadowRaised = [
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

  static const List<BoxShadow> shadowSmall = [
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

  static const List<BoxShadow> shadowInsetLook = [
    BoxShadow(
      color: Color(0x85FFFFFF),
      blurRadius: 6,
      offset: Offset(-3, -3),
    ),
    BoxShadow(
      color: Color(0x99A3B1C6),
      blurRadius: 6,
      offset: Offset(3, 3),
    ),
  ];

  static const List<BoxShadow> shadowAccent = [
    BoxShadow(
      color: Color(0x47544CD2),
      blurRadius: 16,
      offset: Offset(8, 8),
    ),
    BoxShadow(
      color: Color(0x6BFFFFFF),
      blurRadius: 16,
      offset: Offset(-7, -7),
    ),
  ];

  static ThemeData light() {
    const seed = brandBlue;
    return ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: seed),
      useMaterial3: true,
      splashFactory: InkSparkle.splashFactory,
      canvasColor: surface,
      scaffoldBackgroundColor: page,
      appBarTheme: const AppBarTheme(centerTitle: false),
      cardTheme: CardThemeData(
        color: panel,
        elevation: 0,
        surfaceTintColor: panel,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(32),
        ),
      ),
      dividerColor: line,
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: brandBlue, width: 1.4),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: brandBlue,
          foregroundColor: Colors.white,
          minimumSize: const Size(52, 46),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          elevation: 10,
          shadowColor: const Color(0x47544CD2),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          backgroundColor: surface,
          foregroundColor: ink,
          shadowColor: const Color(0x99A3B1C6),
          side: BorderSide.none,
          minimumSize: const Size(52, 46),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          elevation: 8,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
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
          color: ink,
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
}
