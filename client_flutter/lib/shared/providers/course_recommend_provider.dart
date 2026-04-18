import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/recommendation_card.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final courseRecommendProvider =
    FutureProvider.autoDispose<List<RecommendationCardModel>>((ref) async {
  final apiClient = ref.read(apiClientProvider);
  return apiClient.fetchRecommendations();
});
