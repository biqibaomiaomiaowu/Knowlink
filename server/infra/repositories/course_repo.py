from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select 
from server.infra.db.models import Course,ParseRun, VectorDocument
from server.domain.repositories.interfaces import CourseRepository


class SqlAlchemyCourseRepository(CourseRepository): # 建议类名加前缀区分接口
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
    ) -> dict:
        course = Course(
            title=title,
            entry_type=entry_type,
            goal_text=goal_text,
            preferred_style=preferred_style,
            catalog_id=catalog_id,
        )
        self.db.add(course)

        await self.db.commit()
        await self.db.refresh(course)

        return {
            "id": course.id,
            "title": course.title,
            "entry_type": course.entry_type,
            "goal_text": course.goal_text,
            "preferred_style": course.preferred_style,
            "catalog_id": course.catalog_id,
            "created_at": course.created_at,
        }

    async def list_recent_courses(self) -> list[dict]:
        
        result = await self.db.execute(
            select(Course).order_by(Course.created_at.desc()).limit(10)
        )
        courses = result.scalars().all()

        return [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at
            } for c in courses
        ]

    async def get_course_by_id(self, course_id: int) -> Course | None:
        """对接 Service 层 trigger_course_parse 的查询需求[cite: 8]"""
        return await self.db.get(Course, course_id)

    async def create_parse_run(self, course_id: int, status: str) -> ParseRun:
        """
        PR #3 核心接线：创建解析版本记录[cite: 8]
        """
        parse_run = ParseRun(
            course_id=course_id,
            status=status,
            # 默认初始阶段设为 resource_validate
            pipeline_stage="resource_validate" 
        )
        self.db.add(parse_run)
        await self.db.flush() # 使用 flush 拿到 ID 供异步任务使用
        return parse_run

    async def save_handout_outline(self, course_id: int, outline_data: dict):
        """
        PR #3 新增：保存视频优先的讲义大纲
        """
        # 逻辑：更新或插入讲义大纲，设置 generationStatus 为 'ready'
        # 注意：此处应遵循 schemas/ai/handout_outline.schema.json
        pass

    async def insert_vector_documents(self, documents: list[dict]):
        """
        PR #3 关键接线：向量数据写入
        注意：必须使用归一化后的 segment 级 citation
        """
        for doc in documents:
            vec_doc = VectorDocument(
                content=doc["content"],
                embedding=doc["embedding"], # pgvector 格式
                metadata=doc["metadata"]    # 包含 citationSegmentKeys
            )
            self.db.add(vec_doc)
        await self.db.commit()