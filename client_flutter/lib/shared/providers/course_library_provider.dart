import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_lesson_models.dart';
import '../services/course_lesson_api.dart';

final courseLibraryProvider =
    FutureProvider.autoDispose<List<CourseLibraryItemModel>>((ref) {
  return ref.read(courseLessonApiProvider).fetchCourseLibrary();
});
