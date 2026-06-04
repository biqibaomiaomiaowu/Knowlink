import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_lesson_models.dart';
import '../services/course_lesson_api.dart';

final courseWorkbenchProvider = FutureProvider.autoDispose
    .family<CourseWorkbenchModel, String>((ref, courseId) {
  return ref.read(courseLessonApiProvider).fetchCourseWorkbench(courseId);
});
