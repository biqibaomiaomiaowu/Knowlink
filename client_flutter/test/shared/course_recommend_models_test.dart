import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/shared/models/confirm_recommendation_request.dart';
import 'package:knowlink_client/shared/models/confirm_recommendation_result.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/models/recommendation_card.dart';
import 'package:knowlink_client/shared/models/recommendation_enums.dart';
import 'package:knowlink_client/shared/models/recommendation_request.dart';
import 'package:knowlink_client/shared/models/resource_manifest_item.dart';

void main() {
  test('recommendation request serializes examAt and enum fields', () {
    final request = RecommendationRequestModel(
      goalText: '高等数学期末复习',
      selfLevel: SelfLevel.intermediate,
      timeBudgetMinutes: 240,
      examAt: DateTime.utc(2026, 6, 15, 1),
      preferredStyle: PreferredStyle.exam,
    );

    final json = request.toJson();

    expect(json['goalText'], '高等数学期末复习');
    expect(json['selfLevel'], 'intermediate');
    expect(json['timeBudgetMinutes'], 240);
    expect(json['preferredStyle'], 'exam');
    expect(json['examAt'], '2026-06-15T01:00:00.000Z');
  });

  test('confirm request omits nullable fields when absent', () {
    const request = ConfirmRecommendationRequestModel(
      goalText: '高等数学期末复习',
      preferredStyle: PreferredStyle.exam,
    );

    final json = request.toJson();

    expect(json['goalText'], '高等数学期末复习');
    expect(json['preferredStyle'], 'exam');
    expect(json.containsKey('examAt'), isFalse);
    expect(json.containsKey('titleOverride'), isFalse);
  });

  test('recommendation card parses default resource manifest', () {
    final card = RecommendationCardModel.fromJson({
      'catalogId': 'math-final-01',
      'title': '高等数学期末冲刺',
      'provider': 'KnowLink Seed',
      'level': 'intermediate',
      'estimatedHours': 4,
      'fitScore': 96,
      'reasons': ['难度与当前基础匹配'],
      'defaultResourceManifest': [
        {
          'resourceType': 'mp4',
          'required': true,
          'description': '主课程视频',
        },
        {
          'resourceType': 'pptx',
          'required': false,
          'description': '配套课件 PPTX',
        },
      ],
    });

    expect(card.catalogId, 'math-final-01');
    expect(card.defaultResourceManifest, hasLength(2));
    expect(card.defaultResourceManifest.first.resourceType, ResourceType.mp4);
    expect(card.defaultResourceManifest.last.resourceType, ResourceType.pptx);
  });

  test('recommendation card parses reason materials and next action', () {
    final card = RecommendationCardModel.fromJson({
      'catalogId': 'math-final-01',
      'title': '高等数学期末冲刺',
      'provider': 'KnowLink Seed',
      'level': 'intermediate',
      'estimatedHours': 4,
      'fitScore': 96,
      'reasons': ['难度与当前基础匹配'],
      'reasonMaterials': [
        '覆盖高频考点',
        '讲义和视频能组成完整复习闭环',
      ],
      'nextAction': {
        'type': 'confirm_course',
        'label': '确认入课并导入资料',
      },
      'defaultResourceManifest': const [],
    });

    expect(card.reasonMaterials, [
      '覆盖高频考点',
      '讲义和视频能组成完整复习闭环',
    ]);
    expect(card.nextAction.type, 'confirm_course');
    expect(card.nextAction.label, '确认入课并导入资料');
    expect(card.nextAction.canConfirmCourse, isTrue);
  });

  test('recommendation card keeps V1 defaults when V2 fields are absent', () {
    final card = RecommendationCardModel.fromJson({
      'catalogId': 'math-final-01',
      'title': '高等数学期末冲刺',
      'provider': 'KnowLink Seed',
      'level': 'intermediate',
      'estimatedHours': 4,
      'fitScore': 96,
      'reasons': ['难度与当前基础匹配'],
      'defaultResourceManifest': const [],
    });

    expect(card.reasonMaterials, isEmpty);
    expect(card.nextAction.type, 'confirm_course');
    expect(card.nextAction.label, '选择课程并进入导入');
    expect(card.nextAction.canConfirmCourse, isTrue);
  });

  test('confirm result parses course summary payload', () {
    final result = ConfirmRecommendationResultModel.fromJson({
      'course': {
        'courseId': 101,
        'title': '高数期末冲刺课',
        'entryType': 'recommendation',
        'catalogId': 'math-final-01',
        'lifecycleStatus': 'draft',
        'pipelineStage': 'idle',
        'pipelineStatus': 'idle',
        'updatedAt': '2026-04-18T15:00:00+00:00',
      },
      'createdFromCatalogId': 'math-final-01',
    });

    expect(result.createdFromCatalogId, 'math-final-01');
    expect(result.course.courseId, 101);
    expect(result.course.title, '高数期末冲刺课');
    expect(
        result.course.updatedAt, DateTime.parse('2026-04-18T15:00:00+00:00'));
  });

  test('course summary round-trips to json', () {
    final summary = CourseSummaryModel(
      courseId: 101,
      title: '高数期末冲刺课',
      entryType: 'recommendation',
      catalogId: 'math-final-01',
      lifecycleStatus: 'draft',
      pipelineStage: 'idle',
      pipelineStatus: 'idle',
      updatedAt: DateTime.parse('2026-04-18T15:00:00+00:00'),
    );

    final json = summary.toJson();

    expect(json['courseId'], 101);
    expect(json['catalogId'], 'math-final-01');
    expect(json['updatedAt'], '2026-04-18T15:00:00.000Z');
  });

  test('resource manifest item serializes enum name', () {
    const item = ResourceManifestItemModel(
      resourceType: ResourceType.docx,
      isRequired: false,
      description: '补充讲义 DOCX',
    );

    expect(item.toJson(), {
      'resourceType': 'docx',
      'required': false,
      'description': '补充讲义 DOCX',
    });
  });
}
