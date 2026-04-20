import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'router/app_router.dart';
import 'theme/app_theme.dart';

class KnowLinkApp extends StatelessWidget {
  KnowLinkApp({
    super.key,
    GoRouter? routerConfig,
  }) : routerConfig = routerConfig ?? AppRouter.createRouter();

  final GoRouter routerConfig;

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'KnowLink',
      debugShowCheckedModeBanner: false,
      routerConfig: routerConfig,
      theme: AppTheme.light(),
    );
  }
}
