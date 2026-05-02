import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../../shared/models/confirm_recommendation_request.dart';
import '../../shared/models/confirm_recommendation_result.dart';
import '../../shared/models/course_create_request.dart';
import '../../shared/models/course_summary.dart';
import '../../shared/models/inquiry_models.dart';
import '../../shared/models/pipeline_status.dart';
import '../../shared/models/recommendation_card.dart';
import '../../shared/models/recommendation_request.dart';
import '../../shared/models/resource_upload_models.dart';
import '../config/app_config.dart';

class ApiClient {
  ApiClient({
    Dio? dio,
    Dio? objectStorageDio,
    HttpClientAdapter? httpClientAdapter,
    HttpClientAdapter? objectStorageHttpClientAdapter,
    String? baseUrl,
    String? demoToken,
  })  : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: baseUrl ?? AppConfig.apiBaseUrl,
                headers: {
                  'Authorization': 'Bearer ${demoToken ?? AppConfig.demoToken}',
                  'Content-Type': 'application/json',
                },
              ),
            ),
        _objectStorageDio = objectStorageDio ?? Dio() {
    if (httpClientAdapter != null) {
      _dio.httpClientAdapter = httpClientAdapter;
    }
    if (objectStorageHttpClientAdapter != null) {
      _objectStorageDio.httpClientAdapter = objectStorageHttpClientAdapter;
    }
  }

  final Dio _dio;
  final Dio _objectStorageDio;

  Future<List<RecommendationCardModel>> fetchRecommendations(
    RecommendationRequestModel request,
  ) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/recommendations/courses',
      data: request.toJson(),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    final recommendations = data['recommendations'] as List<dynamic>;
    return recommendations
        .map(
          (item) => RecommendationCardModel.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList();
  }

  Future<ConfirmRecommendationResultModel> confirmRecommendation({
    required String catalogId,
    required ConfirmRecommendationRequestModel request,
    required String idempotencyKey,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/recommendations/$catalogId/confirm',
      data: request.toJson(),
      options: Options(
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
      ),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return ConfirmRecommendationResultModel.fromJson(data);
  }

  Future<CourseSummaryModel> createCourse({
    required CourseCreateRequestModel request,
    required String idempotencyKey,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/courses',
      data: request.toJson(),
      options: Options(
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
      ),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return CourseSummaryModel.fromJson(
      Map<String, dynamic>.from(data['course'] as Map),
    );
  }

  Future<ResourceUploadInitResultModel> initResourceUpload({
    required String courseId,
    required ResourceUploadInitRequestModel request,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/courses/$courseId/resources/upload-init',
      data: request.toJson(),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return ResourceUploadInitResultModel.fromJson(data);
  }

  Future<void> uploadObject({
    required String uploadUrl,
    required Uint8List bytes,
    required Map<String, String> headers,
    required String mimeType,
  }) async {
    await _objectStorageDio.putUri<void>(
      Uri.parse(uploadUrl),
      data: bytes,
      options: Options(
        headers: headers,
        contentType: mimeType,
      ),
    );
  }

  Future<CourseResourceModel> completeResourceUpload({
    required String courseId,
    required ResourceUploadCompleteRequestModel request,
    required String idempotencyKey,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/courses/$courseId/resources/upload-complete',
      data: request.toJson(),
      options: Options(
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
      ),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return CourseResourceModel.fromJson(data);
  }

  Future<List<CourseResourceModel>> fetchCourseResources(
      String courseId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/courses/$courseId/resources',
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    final items = data['items'] as List<dynamic>;
    return items
        .map(
          (item) => CourseResourceModel.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList();
  }

  Future<DeleteCourseResourceResultModel> deleteCourseResource({
    required String courseId,
    required int resourceId,
  }) async {
    final response = await _dio.delete<Map<String, dynamic>>(
      '/api/v1/courses/$courseId/resources/$resourceId',
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return DeleteCourseResourceResultModel.fromJson(data);
  }

  Future<ParseStartResultModel> startParse({
    required String courseId,
    required String idempotencyKey,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/courses/$courseId/parse/start',
      options: Options(
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
      ),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return ParseStartResultModel.fromJson(data);
  }

  Future<PipelineStatusModel> fetchPipelineStatus(String courseId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/courses/$courseId/pipeline-status',
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return PipelineStatusModel.fromJson(data);
  }

  Future<InquiryQuestionsModel> fetchInquiryQuestions(String courseId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/courses/$courseId/inquiry/questions',
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return InquiryQuestionsModel.fromJson(data);
  }

  Future<SaveInquiryAnswersResultModel> saveInquiryAnswers({
    required String courseId,
    required SaveInquiryAnswersRequestModel request,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/courses/$courseId/inquiry/answers',
      data: request.toJson(),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return SaveInquiryAnswersResultModel.fromJson(data);
  }
}
