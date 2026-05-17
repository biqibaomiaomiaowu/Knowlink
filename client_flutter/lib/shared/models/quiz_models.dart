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

class QuizModel {
  const QuizModel({
    required this.quizId,
    required this.courseId,
    required this.status,
    required this.questionCount,
    required this.questions,
  });

  final int quizId;
  final int courseId;
  final String status;
  final int questionCount;
  final List<QuizQuestionModel> questions;

  bool get isReady => status == 'ready';

  factory QuizModel.fromJson(Map<String, dynamic> json) {
    return QuizModel(
      quizId: json['quizId'] as int,
      courseId: json['courseId'] as int,
      status: json['status'] as String? ?? 'unknown',
      questionCount: json['questionCount'] as int? ?? 0,
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
  });

  final int questionId;
  final String stemMd;
  final List<String> options;

  factory QuizQuestionModel.fromJson(Map<String, dynamic> json) {
    return QuizQuestionModel(
      questionId: json['questionId'] as int,
      stemMd: json['stemMd'] as String? ?? '',
      options: (json['options'] as List<dynamic>? ?? const [])
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
    this.recommendedReviewAction,
  });

  final int attemptId;
  final int score;
  final int totalScore;
  final double accuracy;
  final int reviewTaskRunId;
  final List<MasteryDeltaModel> masteryDelta;
  final List<QuizAttemptItemResultModel> items;
  final RecommendedReviewActionModel? recommendedReviewAction;

  factory SubmitQuizResultModel.fromJson(Map<String, dynamic> json) {
    return SubmitQuizResultModel(
      attemptId: json['attemptId'] as int,
      score: json['score'] as int? ?? 0,
      totalScore: json['totalScore'] as int? ?? 0,
      accuracy: (json['accuracy'] as num?)?.toDouble() ?? 0,
      reviewTaskRunId: json['reviewTaskRunId'] as int,
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
      recommendedReviewAction: json['recommendedReviewAction'] == null
          ? null
          : RecommendedReviewActionModel.fromJson(
              Map<String, dynamic>.from(
                json['recommendedReviewAction'] as Map,
              ),
            ),
    );
  }
}

class QuizAttemptItemResultModel {
  const QuizAttemptItemResultModel({
    this.questionId,
    this.questionKey,
    this.selectedOption,
    this.correctAnswer,
    this.isCorrect,
    this.obtainedScore,
    this.explanationMd,
    this.knowledgePointKey,
    this.sourceBlockKey,
  });

  final int? questionId;
  final String? questionKey;
  final String? selectedOption;
  final String? correctAnswer;
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
      correctAnswer: json['correctAnswer'] as String?,
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
