import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/widgets/app_scaffold.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'KnowLink',
      body: ListView(
        children: [
          const Text(
            '双入口学习闭环',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: () => context.go('/recommend'),
            child: const Text('进入智能课程推荐'),
          ),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: () => context.go('/import'),
            child: const Text('进入自主导入'),
          ),
          const SizedBox(height: 24),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Text('这里将展示最近学习、Top3 复习任务、今日推荐知识点和学习统计信息。'),
            ),
          ),
        ],
      ),
    );
  }
}
