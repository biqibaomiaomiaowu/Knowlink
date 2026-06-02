import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_lesson_models.dart';
import '../services/course_lesson_api.dart';

class LessonDetailRequest {
  const LessonDetailRequest({
    required this.courseId,
    required this.lessonId,
  });

  final String courseId;
  final String lessonId;

  @override
  bool operator ==(Object other) {
    return other is LessonDetailRequest &&
        other.courseId == courseId &&
        other.lessonId == lessonId;
  }

  @override
  int get hashCode => Object.hash(courseId, lessonId);
}

final lessonDetailProvider = FutureProvider.autoDispose
    .family<LessonDetailModel, LessonDetailRequest>((ref, request) {
  return ref.read(courseLessonApiProvider).fetchLessonDetail(
        courseId: request.courseId,
        lessonId: request.lessonId,
      );
});
