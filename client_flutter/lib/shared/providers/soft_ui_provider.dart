import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/soft_ui_models.dart';

final softUiProvider =
    StateNotifierProvider<SoftUiController, SoftUiState>((ref) {
  return SoftUiController();
});

class SoftUiController extends StateNotifier<SoftUiState> {
  SoftUiController() : super(_initialState());

  void selectCourse(String courseId) {
    final lessonItems = state.lessons[courseId] ?? state.activeCourseLessons;
    final lessonId =
        lessonItems.isEmpty ? state.activeLessonId : lessonItems.first.id;
    state = state.copyWith(
      activeCourseId: courseId,
      activeLessonId: lessonId,
    );
  }

  void selectLesson(String courseId, String lessonId) {
    state = state.copyWith(activeCourseId: courseId, activeLessonId: lessonId);
  }

  SoftCourse createCourse(String title) {
    final now = DateTime.now();
    final id = 'course-${state.courses.length + 1}';
    final lessonId = '$id-lesson-1';
    final lesson = _lesson(
      id: lessonId,
      courseId: id,
      title: '第 1 课：课程导览',
      progress: 0,
      status: '待学习',
    );
    final course = SoftCourse(
      id: id,
      title: title.trim().isEmpty ? '新建课程' : title.trim(),
      progress: 0,
      lessonCount: 1,
      materialCount: 0,
      status: '资料待补充',
      lastStudiedAt: now,
    );
    state = state.copyWith(
      courses: [course, ...state.courses],
      lessons: {...state.lessons, id: [lesson]},
      courseMaterials: {...state.courseMaterials, id: const []},
      activeCourseId: id,
      activeLessonId: lessonId,
      generatedNotices: ['课程已创建，可以继续上传课程资料。'],
    );
    return course;
  }

  void createLesson({
    required String courseId,
    required String title,
    List<String> materialNames = const [],
  }) {
    final current = state.lessons[courseId] ?? const <SoftLesson>[];
    final lessonId = '$courseId-lesson-${current.length + 1}';
    final materials = materialNames
        .map(
          (name) => SoftMaterial(
            id: '$lessonId-material-${name.hashCode.abs()}',
            lessonId: lessonId,
            name: name,
            type: _fileType(name),
            sourceScope: 'lesson',
            citationEnabled: true,
          ),
        )
        .toList();
    final lesson = _lesson(
      id: lessonId,
      courseId: courseId,
      title: title.trim().isEmpty ? '第 ${current.length + 1} 课' : title.trim(),
      progress: 0,
      status: '待学习',
      materials: materials,
    );
    final lessons = {
      ...state.lessons,
      courseId: [...current, lesson],
    };
    final courses = state.courses
        .map(
          (course) => course.id == courseId
              ? SoftCourse(
                  id: course.id,
                  title: course.title,
                  progress: course.progress,
                  lessonCount: course.lessonCount + 1,
                  materialCount: course.materialCount + materials.length,
                  status: '学习中',
                  lastStudiedAt: DateTime.now(),
                )
              : course,
        )
        .toList();
    state = state.copyWith(
      courses: courses,
      lessons: lessons,
      activeCourseId: courseId,
      activeLessonId: lessonId,
      generatedNotices: ['课时已创建，并加入当前课程工作区。'],
    );
  }

  void addCourseMaterial(String courseId, String fileName) {
    final item = SoftMaterial(
      id: '$courseId-course-material-${DateTime.now().microsecondsSinceEpoch}',
      courseId: courseId,
      name: fileName,
      type: _fileType(fileName),
      sourceScope: 'course',
      citationEnabled: true,
    );
    final current = state.courseMaterials[courseId] ?? const <SoftMaterial>[];
    final courses = state.courses
        .map(
          (course) => course.id == courseId
              ? SoftCourse(
                  id: course.id,
                  title: course.title,
                  progress: course.progress,
                  lessonCount: course.lessonCount,
                  materialCount: course.materialCount + 1,
                  status: course.status,
                  lastStudiedAt: DateTime.now(),
                )
              : course,
        )
        .toList();
    state = state.copyWith(
      courses: courses,
      courseMaterials: {...state.courseMaterials, courseId: [item, ...current]},
      generatedNotices: ['课程资料已加入，可用于后续讲义与问答引用。'],
    );
  }

  void addLessonMaterial(String courseId, String lessonId, String fileName) {
    final current = state.lessons[courseId] ?? const <SoftLesson>[];
    final material = SoftMaterial(
      id: '$lessonId-material-${DateTime.now().microsecondsSinceEpoch}',
      lessonId: lessonId,
      name: fileName,
      type: _fileType(fileName),
      sourceScope: 'lesson',
      citationEnabled: true,
    );
    final updated = current
        .map(
          (lesson) => lesson.id == lessonId
              ? lesson.copyWith(materials: [material, ...lesson.materials])
              : lesson,
        )
        .toList();
    state = state.copyWith(
      lessons: {...state.lessons, courseId: updated},
      generatedNotices: ['课时资料已加入本节资料列表。'],
    );
  }

  void generateHandout(String courseId, String lessonId) {
    final current = state.lessons[courseId] ?? const <SoftLesson>[];
    final updated = current.map((lesson) {
      if (lesson.id != lessonId) {
        return lesson;
      }
      final names = lesson.materials.map((item) => item.name).take(4).join('、');
      return lesson.copyWith(
        handout: lesson.handout.copyWith(
          title: '基于资料生成的本节讲义',
          blocks: [
            '核心概念：栈的后进先出、队列的先进先出，以及循环队列的边界判断。',
            '例题拆解：用 front/rear 指针计算队列长度，并解释取模公式。',
            '学习建议：先看视频 08:00-16:30，再完成 10 道中等题巩固。',
          ],
          citations: [
            if (names.isNotEmpty) '来源：$names',
            '引用范围：本节视频、PPT 与课后练习',
          ],
          weakHints: ['循环队列长度计算', '栈与递归调用关系'],
        ),
      );
    }).toList();
    state = state.copyWith(
      lessons: {...state.lessons, courseId: updated},
      generatedNotices: ['已根据本节资料生成讲义。'],
    );
  }

  void sendChat({
    required String text,
    required String scope,
  }) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) {
      return;
    }
    final session = state.activeChatSession;
    final reply = SoftChatMessage(
      role: 'ai',
      content: '我会优先基于$scope回答：$trimmed。关键依据已保留在来源引用里。',
    );
    final sessions = state.chatSessions.map((item) {
      if (item.id != session.id) {
        return item;
      }
      return item.copyWith(
        scope: scope,
        messages: [
          ...item.messages,
          SoftChatMessage(role: 'user', content: trimmed),
          reply,
        ],
        citations: [
          '本节讲义：循环队列边界条件',
          '课程资料：数据结构复习 PPT',
        ],
      );
    }).toList();
    state = state.copyWith(chatSessions: sessions);
  }

  void newChatSession(String scope) {
    final id = 'chat-${state.chatSessions.length + 1}';
    state = state.copyWith(
      chatSessions: [
        SoftChatSession(
          id: id,
          scope: scope,
          messages: const [
            SoftChatMessage(
              role: 'ai',
              content: '新会话已创建。你可以切换范围后继续提问。',
            ),
          ],
          citations: const ['引用将随回答生成'],
        ),
        ...state.chatSessions,
      ],
      activeChatSessionId: id,
    );
  }

  void selectChatSession(String sessionId) {
    state = state.copyWith(activeChatSessionId: sessionId);
  }

  SoftTest generateTest({
    required int questionCount,
    required String difficulty,
  }) {
    final lesson = state.activeLesson;
    final id = 'test-${state.tests.length + 1}';
    final test = SoftTest(
      id: id,
      lessonId: lesson.id,
      courseId: lesson.courseId,
      title: '${lesson.title} 新测验',
      questionCount: questionCount,
      difficulty: difficulty,
      score: null,
      weakPoint: '待完成',
      questions: _questions(questionCount, difficulty),
      createdAt: DateTime.now(),
      elapsedMinutes: 0,
    );
    state = state.copyWith(
      tests: [test, ...state.tests],
      generatedNotices: ['已生成 $questionCount 道$difficulty测验。'],
    );
    return test;
  }

  void regenerateReview() {
    state = state.copyWith(
      generatedNotices: ['今日复习已根据最新测验结果重新生成。'],
    );
  }

  void export(String name) {
    state = state.copyWith(generatedNotices: ['$name 已加入导出任务。']);
  }
}

SoftUiState _initialState() {
  final now = DateTime(2026, 6, 15, 9, 30);
  final courseA = SoftCourse(
    id: 'course-1',
    title: '数据结构期末复习',
    progress: 0.68,
    lessonCount: 6,
    materialCount: 8,
    status: '学习中',
    lastStudiedAt: now,
  );
  final courseB = SoftCourse(
    id: 'course-2',
    title: '操作系统核心概念',
    progress: 0.42,
    lessonCount: 5,
    materialCount: 6,
    status: '复习中',
    lastStudiedAt: DateTime(2026, 6, 14, 20, 10),
  );
  final courseC = SoftCourse(
    id: 'course-3',
    title: '计算机网络速通',
    progress: 0.24,
    lessonCount: 4,
    materialCount: 3,
    status: '资料就绪',
    lastStudiedAt: DateTime(2026, 6, 12, 18, 20),
  );

  final lessons = {
    'course-1': [
      _lesson(
        id: 'lesson-1',
        courseId: 'course-1',
        title: '栈与队列专项复习',
        progress: 0.76,
        status: '学习中',
        materials: const [
          SoftMaterial(
            id: 'mat-1',
            lessonId: 'lesson-1',
            name: 'stack-queue-review.pdf',
            type: 'PDF',
            sourceScope: 'lesson',
            citationEnabled: true,
          ),
          SoftMaterial(
            id: 'mat-2',
            lessonId: 'lesson-1',
            name: 'queue-examples.pptx',
            type: 'PPT',
            sourceScope: 'lesson',
            citationEnabled: true,
          ),
        ],
      ),
      _lesson(
        id: 'lesson-2',
        courseId: 'course-1',
        title: '二叉树遍历与递归',
        progress: 0.52,
        status: '待巩固',
      ),
      _lesson(
        id: 'lesson-3',
        courseId: 'course-1',
        title: '排序算法复杂度',
        progress: 0.35,
        status: '待学习',
      ),
    ],
    'course-2': [
      _lesson(
        id: 'lesson-4',
        courseId: 'course-2',
        title: '进程调度与同步',
        progress: 0.46,
        status: '学习中',
      ),
      _lesson(
        id: 'lesson-5',
        courseId: 'course-2',
        title: '内存管理与页面置换',
        progress: 0.28,
        status: '待学习',
      ),
    ],
    'course-3': [
      _lesson(
        id: 'lesson-6',
        courseId: 'course-3',
        title: 'TCP 握手与拥塞控制',
        progress: 0.24,
        status: '待学习',
      ),
    ],
  };

  return SoftUiState(
    courses: [courseA, courseB, courseC],
    lessons: lessons,
    courseMaterials: const {
      'course-1': [
        SoftMaterial(
          id: 'course-mat-1',
          courseId: 'course-1',
          name: 'data-structure-final-outline.docx',
          type: 'DOC',
          sourceScope: 'course',
          citationEnabled: true,
        ),
        SoftMaterial(
          id: 'course-mat-2',
          courseId: 'course-1',
          name: 'past-exam-questions.pdf',
          type: 'PDF',
          sourceScope: 'course',
          citationEnabled: true,
        ),
      ],
      'course-2': [],
      'course-3': [],
    },
    chatSessions: const [
      SoftChatSession(
        id: 'chat-1',
        scope: '当前课时',
        messages: [
          SoftChatMessage(
            role: 'ai',
            content: '我会引用当前课时资料回答，并在下方保留来源。',
          ),
          SoftChatMessage(
            role: 'user',
            content: '循环队列为什么要空一个位置？',
          ),
          SoftChatMessage(
            role: 'ai',
            content: '这是为了区分队空和队满，避免 front 与 rear 相等时语义冲突。',
          ),
        ],
        citations: ['stack-queue-review.pdf 第 4 页', 'queue-examples.pptx 第 9 页'],
      ),
      SoftChatSession(
        id: 'chat-2',
        scope: '全课程',
        messages: [
          SoftChatMessage(
            role: 'ai',
            content: '可以跨课程资料回答复习问题。',
          ),
        ],
        citations: ['课程讲义索引'],
      ),
    ],
    tests: [
      SoftTest(
        id: 'test-1',
        lessonId: 'lesson-1',
        courseId: 'course-1',
        title: '栈与队列阶段测验',
        questionCount: 15,
        difficulty: '中等',
        score: 86,
        weakPoint: '循环队列',
        questions: _questions(2, '中等'),
        createdAt: DateTime(2026, 6, 14, 21, 10),
      ),
      SoftTest(
        id: 'test-2',
        lessonId: 'lesson-2',
        courseId: 'course-1',
        title: '二叉树遍历小测',
        questionCount: 10,
        difficulty: '基础',
        score: 78,
        weakPoint: '递归边界',
        questions: _questions(2, '基础'),
        createdAt: DateTime(2026, 6, 13, 19, 40),
      ),
    ],
    reviewTasks: const [
      SoftReviewTask(
        id: 'review-1',
        title: '循环队列判空判满',
        sourceLesson: '栈与队列专项复习',
        weakPoints: ['长度公式', '边界条件'],
        estimatedMinutes: 8,
        priority: 1,
        reason: '最近两次测验相关题目错误率较高。',
      ),
      SoftReviewTask(
        id: 'review-2',
        title: '二叉树非递归遍历',
        sourceLesson: '二叉树遍历与递归',
        weakPoints: ['辅助栈', '访问顺序'],
        estimatedMinutes: 12,
        priority: 2,
        reason: '掌握度低于 60%，建议今天补一轮例题。',
      ),
      SoftReviewTask(
        id: 'review-3',
        title: '排序复杂度对比',
        sourceLesson: '排序算法复杂度',
        weakPoints: ['稳定性', '最坏时间复杂度'],
        estimatedMinutes: 10,
        priority: 3,
        reason: '跨章节综合题容易混淆。',
      ),
    ],
    activeCourseId: 'course-1',
    activeLessonId: 'lesson-1',
    activeChatSessionId: 'chat-1',
    generatedNotices: const [],
  );
}

SoftLesson _lesson({
  required String id,
  required String courseId,
  required String title,
  required double progress,
  required String status,
  List<SoftMaterial> materials = const [],
}) {
  return SoftLesson(
    id: id,
    courseId: courseId,
    title: title,
    progress: progress,
    status: status,
    videoUrl: 'mock://lesson-video/$id',
    currentTime: (progress * 2400).round(),
    duration: 2400,
    materials: materials,
    handout: SoftHandout(
      id: '$id-handout',
      lessonId: id,
      title: '本节讲义',
      blocks: const [
        '本节目标：理解栈和队列的核心约束，能把结构特征迁移到题目中。',
        '重点公式：循环队列长度 = (rear - front + maxSize) % maxSize。',
        '易错提醒：队满条件和数组容量不是同一个概念。',
      ],
      citations: const ['stack-queue-review.pdf', 'queue-examples.pptx'],
      weakHints: const ['循环队列长度计算', '递归与栈的关系'],
    ),
  );
}

String _fileType(String name) {
  final ext = name.split('.').last.toLowerCase();
  return switch (ext) {
    'pdf' => 'PDF',
    'ppt' || 'pptx' => 'PPT',
    'doc' || 'docx' => 'DOC',
    'mp4' || 'mov' || 'mkv' || 'avi' => 'MP4',
    'srt' => 'SRT',
    _ => 'FILE',
  };
}

List<SoftQuestion> _questions(int count, String difficulty) {
  final templates = [
    const SoftQuestion(
      title: '循环队列长度的正确计算方式是？',
      options: [
        'A. (rear - front + maxSize) % maxSize',
        'B. rear + front',
        'C. front - rear',
        'D. maxSize - 1',
      ],
      answer: 'A',
    ),
    SoftQuestion(
      title: '$difficulty题：栈在递归调用中的主要作用是什么？',
      options: const [
        'A. 保存调用现场',
        'B. 压缩数据',
        'C. 替代哈希表',
        'D. 提高磁盘吞吐',
      ],
      answer: 'A',
    ),
  ];
  return List.generate(
    count.clamp(1, 20).toInt(),
    (index) => templates[index % templates.length],
  );
}
