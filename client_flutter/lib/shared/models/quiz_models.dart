import 'pipeline_status.dart';

enum QuizQuestionCountLevel {
  small,
  medium,
  large;

  String get apiValue => name;
}

class QuizGenerateResultModel {
  const QuizGenerateResultModel({
    required this.taskId,
    required this.status,
    required this.nextAction,
    required this.entity,
  });

  final int taskId;
  final String status;
  final String nextAction;
  final AsyncEntityModel entity;

  factory QuizGenerateResultModel.fromJson(Map<String, dynamic> json) {
    return QuizGenerateResultModel(
      taskId: json['taskId'] as int,
      status: json['status'] as String,
      nextAction: json['nextAction'] as String,
      entity: AsyncEntityModel.fromJson(
        Map<String, dynamic>.from(json['entity'] as Map),
      ),
    );
  }
}

class QuizStatusModel {
  const QuizStatusModel({
    required this.quizId,
    required this.status,
    required this.questionCount,
    this.courseId,
  });

  final int quizId;
  final int? courseId;
  final String status;
  final int questionCount;

  bool get isReady => status == 'ready';

  factory QuizStatusModel.fromJson(Map<String, dynamic> json) {
    return QuizStatusModel(
      quizId: json['quizId'] as int,
      courseId: json['courseId'] as int?,
      status: json['status'] as String? ?? 'unknown',
      questionCount: json['questionCount'] as int? ?? 0,
    );
  }

  factory QuizStatusModel.fromQuiz(QuizModel quiz) {
    return QuizStatusModel(
      quizId: quiz.quizId,
      courseId: quiz.courseId,
      status: quiz.status,
      questionCount: quiz.questionCount,
    );
  }
}

class CourseQuizHistoryItemModel {
  const CourseQuizHistoryItemModel({
    required this.quizId,
    required this.courseId,
    required this.scopeType,
    required this.status,
    required this.quizMode,
    required this.questionCount,
    this.lessonId,
    this.createdAt,
    this.updatedAt,
    this.latestAttempt,
  });

  final int quizId;
  final int courseId;
  final String scopeType;
  final int? lessonId;
  final String status;
  final String quizMode;
  final int questionCount;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final QuizHistoryAttemptModel? latestAttempt;

  factory CourseQuizHistoryItemModel.fromJson(Map<String, dynamic> json) {
    final latestAttemptJson = json['latestAttempt'] as Map?;
    return CourseQuizHistoryItemModel(
      quizId: json['quizId'] as int,
      courseId: json['courseId'] as int,
      scopeType: json['scopeType'] as String? ?? 'course',
      lessonId: json['lessonId'] as int?,
      status: json['status'] as String? ?? 'unknown',
      quizMode: json['quizMode'] as String? ?? 'objective',
      questionCount: json['questionCount'] as int? ?? 0,
      createdAt: _parseDateTime(json['createdAt']),
      updatedAt: _parseDateTime(json['updatedAt']),
      latestAttempt: latestAttemptJson == null
          ? null
          : QuizHistoryAttemptModel.fromJson(
              Map<String, dynamic>.from(latestAttemptJson),
            ),
    );
  }
}

class QuizHistoryAttemptModel {
  const QuizHistoryAttemptModel({
    required this.attemptId,
    required this.score,
    required this.totalScore,
    required this.accuracy,
    this.reviewTaskRunId,
    this.createdAt,
  });

  final int attemptId;
  final int score;
  final int totalScore;
  final double accuracy;
  final int? reviewTaskRunId;
  final DateTime? createdAt;

  factory QuizHistoryAttemptModel.fromJson(Map<String, dynamic> json) {
    return QuizHistoryAttemptModel(
      attemptId: json['attemptId'] as int,
      score: json['score'] as int? ?? 0,
      totalScore: json['totalScore'] as int? ?? 0,
      accuracy: (json['accuracy'] as num?)?.toDouble() ?? 0,
      reviewTaskRunId: json['reviewTaskRunId'] as int?,
      createdAt: _parseDateTime(json['createdAt']),
    );
  }
}

class QuizModel {
  const QuizModel({
    required this.quizId,
    required this.courseId,
    required this.status,
    required this.questionCount,
    required this.questions,
    this.scopeType = 'course',
    this.lessonId,
    this.startLessonId,
    this.endLessonId,
    this.quizMode = 'objective',
  });

  final int quizId;
  final int courseId;
  final String status;
  final int questionCount;
  final String scopeType;
  final int? lessonId;
  final int? startLessonId;
  final int? endLessonId;
  final String quizMode;
  final List<QuizQuestionModel> questions;

  bool get isReady => status == 'ready';

  factory QuizModel.fromJson(Map<String, dynamic> json) {
    return QuizModel(
      quizId: json['quizId'] as int,
      courseId: json['courseId'] as int,
      status: json['status'] as String? ?? 'unknown',
      questionCount: json['questionCount'] as int? ?? 0,
      scopeType: json['scopeType'] as String? ?? 'course',
      lessonId: json['lessonId'] as int?,
      startLessonId: json['startLessonId'] as int?,
      endLessonId: json['endLessonId'] as int?,
      quizMode: json['quizMode'] as String? ?? 'objective',
      questions: (json['questions'] as List<dynamic>? ?? const [])
          .map(
            (item) => QuizQuestionModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class QuizQuestionModel {
  const QuizQuestionModel({
    required this.questionId,
    required this.stemMd,
    required this.options,
    this.questionType,
    this.knowledgePointKey,
    this.knowledgePointName,
    this.sourceBlockKey,
    this.sourceSegmentKeys = const [],
  });

  final int questionId;
  final String stemMd;
  final List<String> options;
  final String? questionType;
  final String? knowledgePointKey;
  final String? knowledgePointName;
  final String? sourceBlockKey;
  final List<String> sourceSegmentKeys;

  factory QuizQuestionModel.fromJson(Map<String, dynamic> json) {
    return QuizQuestionModel(
      questionId: json['questionId'] as int,
      stemMd: json['stemMd'] as String? ?? '',
      options: (json['options'] as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .toList(),
      questionType: json['questionType'] as String?,
      knowledgePointKey: json['knowledgePointKey'] as String?,
      knowledgePointName: json['knowledgePointName'] as String?,
      sourceBlockKey: json['sourceBlockKey'] as String?,
      sourceSegmentKeys:
          (json['sourceSegmentKeys'] as List<dynamic>? ?? const [])
              .map((item) => item.toString())
              .toList(),
    );
  }
}

class SubmitQuizRequestModel {
  const SubmitQuizRequestModel({
    required this.answers,
  });

  final List<QuizAnswerModel> answers;

  Map<String, dynamic> toJson() {
    return {
      'answers': answers.map((answer) => answer.toJson()).toList(),
    };
  }
}

class QuizAnswerModel {
  const QuizAnswerModel({
    required this.questionId,
    required this.selectedOption,
  });

  final int questionId;
  final String selectedOption;

  Map<String, dynamic> toJson() {
    return {
      'questionId': questionId,
      'selectedOption': selectedOption,
    };
  }
}

class SubmitQuizResultModel {
  const SubmitQuizResultModel({
    required this.attemptId,
    required this.score,
    required this.totalScore,
    required this.accuracy,
    required this.reviewTaskRunId,
    required this.masteryDelta,
    required this.items,
    this.recommendedReviewActions = const [],
  });

  final int attemptId;
  final int score;
  final int totalScore;
  final double accuracy;
  final int? reviewTaskRunId;
  final List<MasteryDeltaModel> masteryDelta;
  final List<QuizAttemptItemResultModel> items;
  final List<RecommendedReviewActionModel> recommendedReviewActions;

  RecommendedReviewActionModel? get recommendedReviewAction =>
      recommendedReviewActions.firstOrNull;

  factory SubmitQuizResultModel.fromJson(Map<String, dynamic> json) {
    final recommendedReviewActionsJson =
        json['recommendedReviewActions'] as List<dynamic>?;
    final legacyRecommendedReviewActionJson =
        json['recommendedReviewAction'] as Map?;
    final recommendedReviewActions = recommendedReviewActionsJson != null
        ? recommendedReviewActionsJson
            .map(
              (item) => RecommendedReviewActionModel.fromJson(
                Map<String, dynamic>.from(item as Map),
              ),
            )
            .toList()
        : legacyRecommendedReviewActionJson == null
            ? <RecommendedReviewActionModel>[]
            : [
                RecommendedReviewActionModel.fromJson(
                  Map<String, dynamic>.from(legacyRecommendedReviewActionJson),
                ),
              ];

    return SubmitQuizResultModel(
      attemptId: json['attemptId'] as int,
      score: json['score'] as int? ?? 0,
      totalScore: json['totalScore'] as int? ?? 0,
      accuracy: (json['accuracy'] as num?)?.toDouble() ?? 0,
      reviewTaskRunId: json['reviewTaskRunId'] as int?,
      masteryDelta: (json['masteryDelta'] as List<dynamic>? ?? const [])
          .map(
            (item) => MasteryDeltaModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      items: (json['items'] as List<dynamic>? ?? const [])
          .map(
            (item) => QuizAttemptItemResultModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      recommendedReviewActions: recommendedReviewActions,
    );
  }
}

class QuizAttemptItemResultModel {
  const QuizAttemptItemResultModel({
    this.questionId,
    this.questionKey,
    this.selectedOption,
    this.isCorrect,
    this.obtainedScore,
    this.explanationMd,
    this.knowledgePointKey,
    this.sourceBlockKey,
  });

  final int? questionId;
  final String? questionKey;
  final String? selectedOption;
  final bool? isCorrect;
  final int? obtainedScore;
  final String? explanationMd;
  final String? knowledgePointKey;
  final String? sourceBlockKey;

  factory QuizAttemptItemResultModel.fromJson(Map<String, dynamic> json) {
    return QuizAttemptItemResultModel(
      questionId: json['questionId'] as int?,
      questionKey: json['questionKey'] as String?,
      selectedOption: json['selectedOption'] as String?,
      isCorrect: json['isCorrect'] as bool?,
      obtainedScore: json['obtainedScore'] as int?,
      explanationMd: json['explanationMd'] as String?,
      knowledgePointKey: json['knowledgePointKey'] as String?,
      sourceBlockKey: json['sourceBlockKey'] as String?,
    );
  }
}

class MasteryDeltaModel {
  const MasteryDeltaModel({
    required this.knowledgePoint,
    required this.delta,
    required this.status,
  });

  final String knowledgePoint;
  final double delta;
  final String status;

  factory MasteryDeltaModel.fromJson(Map<String, dynamic> json) {
    return MasteryDeltaModel(
      knowledgePoint: json['knowledgePoint'] as String? ?? '知识点',
      delta: (json['delta'] as num?)?.toDouble() ?? 0,
      status: json['status'] as String? ?? 'unknown',
    );
  }
}

class RecommendedReviewActionModel {
  const RecommendedReviewActionModel({
    required this.type,
    required this.reason,
    this.targetBlockId,
    this.targetId,
  });

  final String type;
  final String reason;
  final int? targetBlockId;
  final int? targetId;

  factory RecommendedReviewActionModel.fromJson(Map<String, dynamic> json) {
    return RecommendedReviewActionModel(
      type: json['type'] as String? ?? 'review',
      reason: json['reason'] as String? ?? '',
      targetBlockId: json['targetBlockId'] as int?,
      targetId: json['targetId'] as int?,
    );
  }
}

DateTime? _parseDateTime(Object? value) {
  if (value is! String || value.isEmpty) {
    return null;
  }
  return DateTime.tryParse(value);
}
