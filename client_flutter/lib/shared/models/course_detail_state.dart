import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'course_summary.dart';

class CourseDetailState {
  const CourseDetailState({
    this.course = const AsyncData(null),
    this.currentCourse = const AsyncData(null),
    this.currentCourseSwitch = const AsyncData(null),
  });

  final AsyncValue<CourseSummaryModel?> course;
  final AsyncValue<CourseSummaryModel?> currentCourse;
  final AsyncValue<CourseSummaryModel?> currentCourseSwitch;

  CourseDetailState copyWith({
    AsyncValue<CourseSummaryModel?>? course,
    AsyncValue<CourseSummaryModel?>? currentCourse,
    AsyncValue<CourseSummaryModel?>? currentCourseSwitch,
  }) {
    return CourseDetailState(
      course: course ?? this.course,
      currentCourse: currentCourse ?? this.currentCourse,
      currentCourseSwitch: currentCourseSwitch ?? this.currentCourseSwitch,
    );
  }
}
