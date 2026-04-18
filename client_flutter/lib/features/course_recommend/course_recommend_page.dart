import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/widgets/app_scaffold.dart';
import '../../shared/providers/course_recommend_provider.dart';

class CourseRecommendPage extends ConsumerWidget {
  const CourseRecommendPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recommendations = ref.watch(courseRecommendProvider);

    return AppScaffold(
      title: '智能课程推荐',
      body: recommendations.when(
        data: (items) => ListView.separated(
          itemBuilder: (context, index) {
            final item = items[index];
            return Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Text('${item.provider} · ${item.level} · ${item.estimatedHours}h'),
                    const SizedBox(height: 8),
                    Text('匹配度 ${item.fitScore}'),
                    const SizedBox(height: 8),
                    for (final reason in item.reasons) Text('• $reason'),
                  ],
                ),
              ),
            );
          },
          separatorBuilder: (context, index) => const SizedBox(height: 12),
          itemCount: items.length,
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stackTrace) => Center(
          child: Text('推荐接口暂不可用：$error'),
        ),
      ),
    );
  }
}
