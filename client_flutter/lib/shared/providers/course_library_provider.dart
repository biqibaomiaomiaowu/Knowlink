import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/course_lesson_models.dart';
import '../services/course_lesson_api.dart';

const Object _unset = Object();

class CourseLibraryQuery {
  const CourseLibraryQuery({
    this.query,
    this.learningStatus,
    this.source,
    this.archived = 'exclude',
    this.sort = 'recent_activity_desc',
  });

  final String? query;
  final String? learningStatus;
  final String? source;
  final String archived;
  final String sort;

  CourseLibraryQuery copyWith({
    Object? query = _unset,
    Object? learningStatus = _unset,
    Object? source = _unset,
    String? archived,
    String? sort,
  }) {
    return CourseLibraryQuery(
      query: identical(query, _unset) ? this.query : query as String?,
      learningStatus: identical(learningStatus, _unset)
          ? this.learningStatus
          : learningStatus as String?,
      source: identical(source, _unset) ? this.source : source as String?,
      archived: archived ?? this.archived,
      sort: sort ?? this.sort,
    );
  }
}

final courseLibraryQueryProvider =
    StateProvider.autoDispose<CourseLibraryQuery>((ref) {
  return const CourseLibraryQuery();
});

final courseLibraryProvider =
    FutureProvider.autoDispose<List<CourseLibraryItemModel>>((ref) {
  final query = ref.watch(courseLibraryQueryProvider);
  return ref.read(courseLessonApiProvider).fetchCourseLibrary(
        query: query.query,
        learningStatus: query.learningStatus,
        source: query.source,
        archived: query.archived,
        sort: query.sort,
      );
});
