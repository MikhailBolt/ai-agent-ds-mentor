def upsert_user(user_id: int, username: str, first_name: str, last_name: str = "") -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO users (user_id, username, first_name, last_name, updated_at)
    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(user_id) DO UPDATE SET
        username = excluded.username,
        first_name = excluded.first_name,
        last_name = excluded.last_name,
        updated_at = CURRENT_TIMESTAMP
    """, (user_id, username, first_name, last_name))

    conn.commit()
    conn.close()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_user_profile(
    user_id: int,
    goal: Optional[str] = None,
    level: Optional[str] = None,
    daily_minutes: Optional[int] = None,
    strengths: Optional[List[str]] = None,
    weak_topics: Optional[List[str]] = None,
    completed_topics: Optional[List[str]] = None,
    current_plan: Optional[str] = None,
    notifications_enabled: Optional[bool] = None,
) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    fields = []
    values: List[Any] = []

    if goal is not None:
        fields.append("goal = ?")
        values.append(goal)

    if level is not None:
        fields.append("level = ?")
        values.append(level)

    if daily_minutes is not None:
        fields.append("daily_minutes = ?")
        values.append(daily_minutes)

    if strengths is not None:
        fields.append("strengths_json = ?")
        values.append(json.dumps(strengths, ensure_ascii=False))

    if weak_topics is not None:
        fields.append("weak_topics_json = ?")
        values.append(json.dumps(weak_topics, ensure_ascii=False))

    if completed_topics is not None:
        fields.append("completed_topics_json = ?")
        values.append(json.dumps(completed_topics, ensure_ascii=False))

    if current_plan is not None:
        fields.append("current_plan = ?")
        values.append(current_plan)

    if notifications_enabled is not None:
        fields.append("notifications_enabled = ?")
        values.append(1 if notifications_enabled else 0)

    fields.append("updated_at = CURRENT_TIMESTAMP")

    values.append(user_id)

    cur.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?",
        values
    )
    conn.commit()
    conn.close()


def create_quiz_session(
    user_id: int,
    topic: str,
    questions: List[Dict[str, Any]],
    difficulty: str = "medium",
) -> int:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO quiz_sessions (user_id, topic, questions_json, current_index, score, difficulty, status)
    VALUES (?, ?, ?, 0, 0, ?, 'active')
    """, (user_id, topic, json.dumps(questions, ensure_ascii=False), difficulty))

    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_active_quiz_session(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM quiz_sessions
    WHERE user_id = ? AND status = 'active'
    ORDER BY id DESC
    LIMIT 1
    """, (user_id,))

    row = cur.fetchone()
    conn.close()
    return row


def update_quiz_session(session_id: int, current_index: int, score: int, status: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    completed_at = datetime.now().isoformat() if status == "completed" else None

    cur.execute("""
    UPDATE quiz_sessions
    SET current_index = ?,
        score = ?,
        status = ?,
        completed_at = CASE WHEN ? IS NOT NULL THEN ? ELSE completed_at END
    WHERE id = ?
    """, (current_index, score, status, completed_at, completed_at, session_id))

    conn.commit()
    conn.close()


def save_quiz_answer(
    quiz_session_id: int,
    question_index: int,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    feedback: str,
    response_time: int = 0,
) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO quiz_answers (
        quiz_session_id, question_index, user_answer, correct_answer, is_correct, feedback, response_time
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        quiz_session_id,
        question_index,
        user_answer,
        correct_answer,
        1 if is_correct else 0,
        feedback,
        response_time,
    ))

    conn.commit()
    conn.close()


def maybe_award_quiz_achievements(user_id: int, score: int, total: int) -> List[str]:
    awarded = []

    if check_and_award_achievement(user_id, "first_quiz", "Первый завершённый квиз"):
        awarded.append("🏆 Достижение: Первый завершённый квиз")

    if total > 0 and score == total:
        if check_and_award_achievement(user_id, "perfect_quiz", "Идеальный результат в квизе"):
            awarded.append("🏆 Достижение: Идеальный результат в квизе")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT COUNT(*) as total_correct
    FROM quiz_answers qa
    JOIN quiz_sessions qs ON qa.quiz_session_id = qs.id
    WHERE qs.user_id = ? AND qa.is_correct = 1
    """, (user_id,))
    total_correct = cur.fetchone()["total_correct"]
    conn.close()

    if total_correct >= 10:
        if check_and_award_achievement(user_id, "correct_10", "10 правильных ответов"):
            awarded.append("🏆 Достижение: 10 правильных ответов")

    return awarded


def send_next_quiz_question(chat_id: int, user_id: int) -> None:
    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "У тебя нет активного квиза. Запусти: /quiz <тема>")
        return

    questions = json.loads(session["questions_json"])
    current_index = safe_parse_int(session["current_index"], 0)

    if current_index >= len(questions):
        score = safe_parse_int(session["score"], 0)
        total = len(questions)
        update_quiz_session(session["id"], current_index, score, "completed")

        achievements = maybe_award_quiz_achievements(user_id, score, total)
        text = f"✅ Квиз завершён!\n\nРезультат: {score}/{total}"
        if achievements:
            text += "\n\n" + "\n".join(achievements)

        telegram_send_message(chat_id, text)
        log_study_event(
            user_id,
            "quiz_completed",
            topic=session["topic"],
            payload={"score": score, "total": total, "difficulty": session["difficulty"]},
        )
        update_study_time(user_id, 15, session["topic"])
        return

    question = questions[current_index]
    options_text = "\n".join([f"• {opt}" for opt in question["options"]])

    hint_line = ""
    if question.get("hint"):
        hint_line = "\nПодсказка: /hint"

    text = (
        f"<b>Вопрос {current_index + 1}/{len(questions)}</b>\n"
        f"Тема: {session['topic']}\n"
        f"Сложность: {session['difficulty']}\n\n"
        f"{question['question']}\n\n"
        f"{options_text}\n\n"
        f"Ответь так:\n"
        f"/answer <вариант>\n"
        f"/skip — пропустить вопрос"
        f"{hint_line}"
    )
    telegram_send_message(chat_id, text)


def handle_hint(chat_id: int, user_id: int) -> None:
    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "Нет активного квиза.")
        return

    questions = json.loads(session["questions_json"])
    current_index = safe_parse_int(session["current_index"], 0)
    if current_index >= len(questions):
        telegram_send_message(chat_id, "Квиз уже завершён.")
        return

    question = questions[current_index]
    hint = question.get("hint", "")
    if not hint:
        telegram_send_message(chat_id, "Для этого вопроса подсказка недоступна.")
        return

    telegram_send_message(chat_id, f"💡 Подсказка:\n{hint}")


def handle_skip(chat_id: int, user_id: int) -> None:
    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "Нет активного квиза.")
        return

    current_index = safe_parse_int(session["current_index"], 0)
    score = safe_parse_int(session["score"], 0)

    save_quiz_answer(
        quiz_session_id=session["id"],
        question_index=current_index,
        user_answer="__skipped__",
        correct_answer="",
        is_correct=False,
        feedback="Вопрос был пропущен.",
        response_time=0,
    )

    update_quiz_session(session["id"], current_index + 1, score, "active")
    telegram_send_message(chat_id, "⏭ Вопрос пропущен.")
    send_next_quiz_question(chat_id, user_id)


def handle_answer(chat_id: int, user_id: int, user_answer: str) -> None:
    user_answer = user_answer.strip()
    if not user_answer:
        telegram_send_message(chat_id, "Используй: /answer <вариант>")
        return

    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "Нет активного квиза. Запусти: /quiz <тема>")
        return

    questions = json.loads(session["questions_json"])
    current_index = safe_parse_int(session["current_index"], 0)

    if current_index >= len(questions):
        telegram_send_message(chat_id, "Квиз уже завершён.")
        return

    question = questions[current_index]
    correct_answer = question["correct_answer"]
    explanation = question["explanation"]

    is_correct, feedback, review_meta = reviewer_agent(
        question=question["question"],
        correct_answer=correct_answer,
        explanation=explanation,
        user_answer=user_answer,
    )

    new_score = safe_parse_int(session["score"], 0) + (1 if is_correct else 0)
    new_index = current_index + 1
    new_status = "completed" if new_index >= len(questions) else "active"

    save_quiz_answer(
        quiz_session_id=session["id"],
        question_index=current_index,
        user_answer=user_answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
        feedback=feedback,
        response_time=0,
    )

    update_quiz_session(session["id"], new_index, new_score, new_status)

    log_study_event(
        user_id,
        "quiz_answered",
        topic=session["topic"],
        payload={
            "question": question["question"],
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "review_meta": review_meta,
        },
    )

    telegram_send_message(chat_id, feedback[:4000])

    if new_status == "completed":
        send_next_quiz_question(chat_id, user_id)
    else:
        send_next_quiz_question(chat_id, user_id)