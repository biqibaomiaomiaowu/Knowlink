class SoftCourse {
  const SoftCourse({
    required this.id,
    required this.title,
    required this.progress,
    required this.lessonCount,
    required this.materialCount,
    required this.status,
    required this.lastStudiedAt,
  });

  final String id;
  final String title;
  final double progress;
  final int lessonCount;
  final int materialCount;
  final String status;
  final DateTime lastStudiedAt;
}

class SoftLesson {
  const SoftLesson({
    required this.id,
    required this.courseId,
    required this.title,
    required this.progress,
    required this.status,
    required this.videoUrl,
    required this.currentTime,
    required this.duration,
    required this.materials,
    required this.handout,
  });

  final String id;
  final String courseId;
  final String title;
  final double progress;
  final String status;
  final String videoUrl;
  final int currentTime;
  final int duration;
  final List<SoftMaterial> materials;
  final SoftHandout handout;

  SoftLesson copyWith({
    String? id,
    String? courseId,
    String? title,
    double? progress,
    String? status,
    String? videoUrl,
    int? currentTime,
    int? duration,
    List<SoftMaterial>? materials,
    SoftHandout? handout,
  }) {
    return SoftLesson(
      id: id ?? this.id,
      courseId: courseId ?? this.courseId,
      title: title ?? this.title,
      progress: progress ?? this.progress,
      status: status ?? this.status,
      videoUrl: videoUrl ?? this.videoUrl,
      currentTime: currentTime ?? this.currentTime,
      duration: duration ?? this.duration,
      materials: materials ?? this.materials,
      handout: handout ?? this.handout,
    );
  }
}

class SoftMaterial {
  const SoftMaterial({
    required this.id,
    required this.name,
    required this.type,
    required this.sourceScope,
    required this.citationEnabled,
    this.courseId,
    this.lessonId,
  });

  final String id;
  final String? lessonId;
  final String? courseId;
  final String name;
  final String type;
  final String sourceScope;
  final bool citationEnabled;
}

class SoftHandout {
  const SoftHandout({
    required this.id,
    required this.lessonId,
    required this.title,
    required this.blocks,
    required this.citations,
    required this.weakHints,
  });

  final String id;
  final String lessonId;
  final String title;
  final List<String> blocks;
  final List<String> citations;
  final List<String> weakHints;

  SoftHandout copyWith({
    String? id,
    String? lessonId,
    String? title,
    List<String>? blocks,
    List<String>? citations,
    List<String>? weakHints,
  }) {
    return SoftHandout(
      id: id ?? this.id,
      lessonId: lessonId ?? this.lessonId,
      title: title ?? this.title,
      blocks: blocks ?? this.blocks,
      citations: citations ?? this.citations,
      weakHints: weakHints ?? this.weakHints,
    );
  }
}

class SoftChatSession {
  const SoftChatSession({
    required this.id,
    required this.scope,
    required this.messages,
    required this.citations,
  });

  final String id;
  final String scope;
  final List<SoftChatMessage> messages;
  final List<String> citations;

  SoftChatSession copyWith({
    String? id,
    String? scope,
    List<SoftChatMessage>? messages,
    List<String>? citations,
  }) {
    return SoftChatSession(
      id: id ?? this.id,
      scope: scope ?? this.scope,
      messages: messages ?? this.messages,
      citations: citations ?? this.citations,
    );
  }
}

class SoftChatMessage {
  const SoftChatMessage({
    required this.role,
    required this.content,
  });

  final String role;
  final String content;
}

class SoftTest {
  const SoftTest({
    required this.id,
    required this.title,
    required this.questionCount,
    required this.difficulty,
    required this.score,
    required this.weakPoint,
    required this.questions,
    required this.createdAt,
    this.lessonId,
    this.courseId,
    this.elapsedMinutes = 18,
  });

  final String id;
  final String? lessonId;
  final String? courseId;
  final String title;
  final int questionCount;
  final String difficulty;
  final int? score;
  final String weakPoint;
  final List<SoftQuestion> questions;
  final DateTime createdAt;
  final int elapsedMinutes;
}

class SoftQuestion {
  const SoftQuestion({
    required this.title,
    required this.options,
    this.answer,
  });

  final String title;
  final List<String> options;
  final String? answer;
}

class SoftReviewTask {
  const SoftReviewTask({
    required this.id,
    required this.title,
    required this.sourceLesson,
    required this.weakPoints,
    required this.estimatedMinutes,
    required this.priority,
    required this.reason,
  });

  final String id;
  final String title;
  final String sourceLesson;
  final List<String> weakPoints;
  final int estimatedMinutes;
  final int priority;
  final String reason;
}

class SoftUiState {
  const SoftUiState({
    required this.courses,
    required this.lessons,
    required this.courseMaterials,
    required this.chatSessions,
    required this.tests,
    required this.reviewTasks,
    required this.activeCourseId,
    required this.activeLessonId,
    required this.activeChatSessionId,
    required this.generatedNotices,
  });

  final List<SoftCourse> courses;
  final Map<String, List<SoftLesson>> lessons;
  final Map<String, List<SoftMaterial>> courseMaterials;
  final List<SoftChatSession> chatSessions;
  final List<SoftTest> tests;
  final List<SoftReviewTask> reviewTasks;
  final String activeCourseId;
  final String activeLessonId;
  final String activeChatSessionId;
  final List<String> generatedNotices;

  SoftCourse get activeCourse {
    return courses.firstWhere(
      (course) => course.id == activeCourseId,
      orElse: () => courses.first,
    );
  }

  List<SoftLesson> get activeCourseLessons {
    return lessons[activeCourseId] ?? const [];
  }

  SoftLesson get activeLesson {
    final items = activeCourseLessons;
    final fallbackItems = lessons.values.expand((item) => item).toList();
    return items.firstWhere(
      (lesson) => lesson.id == activeLessonId,
      orElse: () => fallbackItems.first,
    );
  }

  SoftChatSession get activeChatSession {
    return chatSessions.firstWhere(
      (session) => session.id == activeChatSessionId,
      orElse: () => chatSessions.first,
    );
  }

  SoftUiState copyWith({
    List<SoftCourse>? courses,
    Map<String, List<SoftLesson>>? lessons,
    Map<String, List<SoftMaterial>>? courseMaterials,
    List<SoftChatSession>? chatSessions,
    List<SoftTest>? tests,
    List<SoftReviewTask>? reviewTasks,
    String? activeCourseId,
    String? activeLessonId,
    String? activeChatSessionId,
    List<String>? generatedNotices,
  }) {
    return SoftUiState(
      courses: courses ?? this.courses,
      lessons: lessons ?? this.lessons,
      courseMaterials: courseMaterials ?? this.courseMaterials,
      chatSessions: chatSessions ?? this.chatSessions,
      tests: tests ?? this.tests,
      reviewTasks: reviewTasks ?? this.reviewTasks,
      activeCourseId: activeCourseId ?? this.activeCourseId,
      activeLessonId: activeLessonId ?? this.activeLessonId,
      activeChatSessionId: activeChatSessionId ?? this.activeChatSessionId,
      generatedNotices: generatedNotices ?? this.generatedNotices,
    );
  }
}
