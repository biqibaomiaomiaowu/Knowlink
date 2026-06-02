import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/course_lesson_models.dart';
import '../providers/course_recommend_provider.dart';

final courseLessonApiProvider = Provider<CourseLessonApi>((ref) {
  return CourseLessonApi(ref.read(apiClientProvider));
});

class CourseLessonApi {
  const CourseLessonApi(this._client);

  final ApiClient _client;

  Future<List<CourseLibraryItemModel>> fetchCourseLibrary({
    String? query,
    String? learningStatus,
    String? source,
    String archived = 'exclude',
    String sort = 'recent_activity_desc',
  }) {
    return _client.fetchCourseLibrary(
      query: query,
      learningStatus: learningStatus,
      source: source,
      archived: archived,
      sort: sort,
    );
  }

  Future<CourseWorkbenchModel> fetchCourseWorkbench(String courseId) {
    return _client.fetchCourseWorkbench(courseId);
  }

  Future<List<LessonSummaryModel>> fetchLessons(String courseId) {
    return _client.fetchLessons(courseId);
  }

  Future<LessonDetailModel> fetchLessonDetail({
    required String courseId,
    required String lessonId,
  }) {
    return _client.fetchLessonDetail(courseId: courseId, lessonId: lessonId);
  }

  Future<LessonSummaryModel> createLesson({
    required String courseId,
    required Map<String, dynamic> request,
    String? idempotencyKey,
  }) {
    return _client.createLesson(
      courseId: courseId,
      request: request,
      idempotencyKey: idempotencyKey,
    );
  }

  Future<LessonSummaryModel> updateLesson({
    required String courseId,
    required String lessonId,
    required Map<String, dynamic> request,
  }) {
    return _client.updateLesson(
      courseId: courseId,
      lessonId: lessonId,
      request: request,
    );
  }

  Future<void> deleteLesson({
    required String courseId,
    required String lessonId,
  }) {
    return _client.deleteLesson(courseId: courseId, lessonId: lessonId);
  }

  Future<List<LessonSummaryModel>> reorderLessons({
    required String courseId,
    required List<String> lessonIds,
  }) {
    return _client.reorderLessons(courseId: courseId, lessonIds: lessonIds);
  }

  Future<LessonSummaryModel> setLessonPrimaryVideo({
    required String courseId,
    required String lessonId,
    required String resourceId,
    required int startSec,
    required int endSec,
  }) {
    return _client.setLessonPrimaryVideo(
      courseId: courseId,
      lessonId: lessonId,
      resourceId: resourceId,
      startSec: startSec,
      endSec: endSec,
    );
  }

  Future<Map<String, dynamic>> mergeLessons({
    required String courseId,
    required List<String> lessonIds,
    String? targetTitle,
  }) {
    return _client.mergeLessons(
      courseId: courseId,
      lessonIds: lessonIds,
      targetTitle: targetTitle,
    );
  }

  Future<Map<String, dynamic>> splitLesson({
    required String courseId,
    required String lessonId,
    required int splitAtSec,
    String? firstTitle,
    String? secondTitle,
  }) {
    return _client.splitLesson(
      courseId: courseId,
      lessonId: lessonId,
      splitAtSec: splitAtSec,
      firstTitle: firstTitle,
      secondTitle: secondTitle,
    );
  }

  Future<LessonProgressModel> fetchLessonProgress({
    required String courseId,
    required String lessonId,
  }) {
    return _client.fetchLessonProgress(courseId: courseId, lessonId: lessonId);
  }

  Future<LessonProgressModel> updateLessonProgress({
    required String courseId,
    required String lessonId,
    required Map<String, dynamic> request,
  }) {
    return _client.updateLessonProgress(
      courseId: courseId,
      lessonId: lessonId,
      request: request,
    );
  }

  Future<PlaceholderEntryModel> fetchCourseQaPlaceholder(String courseId) {
    return _client.fetchCourseQaPlaceholder(courseId);
  }

  Future<PlaceholderEntryModel> fetchLessonQaPlaceholder({
    required String courseId,
    required String lessonId,
  }) {
    return _client.fetchLessonQaPlaceholder(
      courseId: courseId,
      lessonId: lessonId,
    );
  }

  Future<PlaceholderEntryModel> fetchCourseGraphPlaceholder(String courseId) {
    return _client.fetchCourseGraphPlaceholder(courseId);
  }

  Future<PlaceholderEntryModel> fetchLessonGraphPlaceholder({
    required String courseId,
    required String lessonId,
  }) {
    return _client.fetchLessonGraphPlaceholder(
      courseId: courseId,
      lessonId: lessonId,
    );
  }

  Future<PlaceholderEntryModel> fetchCourseExportPlaceholder(String courseId) {
    return _client.fetchCourseExportPlaceholder(courseId);
  }
}
