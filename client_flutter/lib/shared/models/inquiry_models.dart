class InquiryQuestionOptionModel {
  const InquiryQuestionOptionModel({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  factory InquiryQuestionOptionModel.fromJson(Map<String, dynamic> json) {
    return InquiryQuestionOptionModel(
      label: json['label'] as String,
      value: json['value'] as String,
    );
  }
}

class InquiryQuestionModel {
  const InquiryQuestionModel({
    required this.key,
    required this.label,
    required this.type,
    required this.isRequired,
    required this.options,
  });

  final String key;
  final String label;
  final String type;
  final bool isRequired;
  final List<InquiryQuestionOptionModel> options;

  factory InquiryQuestionModel.fromJson(Map<String, dynamic> json) {
    return InquiryQuestionModel(
      key: json['key'] as String,
      label: json['label'] as String,
      type: json['type'] as String,
      isRequired: json['required'] as bool? ?? false,
      options: (json['options'] as List<dynamic>? ?? const [])
          .map(
            (item) => InquiryQuestionOptionModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class InquiryQuestionsModel {
  const InquiryQuestionsModel({
    required this.version,
    required this.questions,
  });

  final int version;
  final List<InquiryQuestionModel> questions;

  factory InquiryQuestionsModel.fromJson(Map<String, dynamic> json) {
    return InquiryQuestionsModel(
      version: json['version'] as int,
      questions: (json['questions'] as List<dynamic>? ?? const [])
          .map(
            (item) => InquiryQuestionModel.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class InquiryAnswerModel {
  const InquiryAnswerModel({
    required this.key,
    required this.value,
  });

  final String key;
  final Object value;

  Map<String, dynamic> toJson() {
    return {
      'key': key,
      'value': value,
    };
  }
}

class SaveInquiryAnswersRequestModel {
  const SaveInquiryAnswersRequestModel({
    required this.answers,
  });

  final List<InquiryAnswerModel> answers;

  Map<String, dynamic> toJson() {
    return {
      'answers': answers.map((answer) => answer.toJson()).toList(),
    };
  }
}

class SaveInquiryAnswersResultModel {
  const SaveInquiryAnswersResultModel({
    required this.saved,
    required this.answerCount,
  });

  final bool saved;
  final int answerCount;

  factory SaveInquiryAnswersResultModel.fromJson(Map<String, dynamic> json) {
    return SaveInquiryAnswersResultModel(
      saved: json['saved'] as bool,
      answerCount: json['answerCount'] as int,
    );
  }
}
