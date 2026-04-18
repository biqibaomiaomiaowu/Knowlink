import 'package:dio/dio.dart';

import '../../shared/models/recommendation_card.dart';
import '../config/app_config.dart';

class ApiClient {
  ApiClient()
      : _dio = Dio(
          BaseOptions(
            baseUrl: AppConfig.apiBaseUrl,
            headers: {
              'Authorization': 'Bearer ${AppConfig.demoToken}',
              'Content-Type': 'application/json',
            },
          ),
        );

  final Dio _dio;

  Future<List<RecommendationCardModel>> fetchRecommendations() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/recommendations/courses',
      data: {
        'goalText': '高等数学期末复习',
        'selfLevel': 'intermediate',
        'timeBudgetMinutes': 240,
        'preferredStyle': 'exam',
      },
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
}
