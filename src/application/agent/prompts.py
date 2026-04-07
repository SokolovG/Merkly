LANG_SOURCES: dict[str, list[str]] = {
    "de": [
        "https://www.tagesschau.de/xml/rss2/",
        "https://rss.dw.com/rdf/rss-de-news",
        "https://www.spiegel.de/schlagzeilen/index.rss",
    ],
    "en": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.reuters.com/reuters/topNews",
    ],
    "es": [
        "https://www.bbc.com/mundo/index.xml",
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    ],
    "fr": [
        "https://www.france24.com/fr/rss",
        "https://www.lemonde.fr/rss/une.xml",
    ],
    "it": ["https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml"],
    "pt": ["https://g1.globo.com/rss/g1/"],
}

LANG_NAMES: dict[str, str] = {
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "zh": "Chinese",
}


def lang_name(code: str) -> str:
    # If it's a known code, return the name. Otherwise use as-is (user typed full name).
    return LANG_NAMES.get(code.lower(), code)


def build_system_prompt(target_lang: str) -> str:
    name = lang_name(target_lang)
    sources = LANG_SOURCES.get(target_lang, LANG_SOURCES.get("en", []))
    sources_str = "\n".join(f"  {i + 1}. {url}" for i, url in enumerate(sources))
    source_section = (
        (
            f"\nAvailable {name} news sources (try in order, pass as source_url):\n{sources_str}\n"
            "If one source fails, call fetch_article again with the next source_url. "
            "Keep trying until an article is successfully fetched."
        )
        if sources_str
        else ""
    )
    return (
        f"You are a {name} language tutor. Your job is to run a structured daily lesson "
        f"for a student learning {name}. You have access to tools to fetch articles, "
        "generate questions, review answers, and create flashcards.\n\n"
        f"Always respond in {name} when asking comprehension questions or giving feedback "
        f"(unless instructed otherwise). Adapt to the student's level and goal. "
        "Be encouraging but precise about mistakes. "
        "When creating flashcards, focus on vocabulary the student actually struggled with."
        f"{source_section}"
    )


def build_lesson_prompt(
    level: str,
    goal: str,
    native_lang: str,
    target_lang: str,
    session_minutes: int,
    recent_sessions: list[str],
) -> str:
    history_note = ""
    if recent_sessions:
        topics = ", ".join(recent_sessions[-3:])
        history_note = f"\nRecent session topics: {topics}. Pick a different topic."

    name = lang_name(target_lang)
    return f"""
Start a {name} lesson for this student:
- Level: {level}
- Goal: {goal}
- Native language: {native_lang}
- Session duration: {session_minutes} minutes
{history_note}

Steps:
1. Fetch a {name} article appropriate for level {level}
2. Generate 3 comprehension questions IN {name.upper()}
3. Wait for the student to answer (the answers will come as a follow-up message)
4. Review the answers and give feedback
5. Create flashcards for any vocabulary gaps you identified

Start by fetching the article now.
""".strip()


def build_vocab_prompt(level: str, target_lang: str, native_lang: str, count: int = 8) -> str:
    name = lang_name(target_lang)
    native_name = lang_name(native_lang)
    _card_str = "card" if count == 1 else "cards"
    return f"""
Fetch a {name} news article suitable for level {level}.
Then extract exactly {count} vocabulary words or phrases from the article that are useful for a {level} student.
For each word, call create_flash_card with the word, its {native_name} translation, and an example sentence from the article.
Focus on words that are at or slightly above {level} difficulty.
Do not ask any questions. Just fetch the article and create the {count} {_card_str}.
""".strip()


GOAL_TOPICS: dict[str, list[str]] = {
    "study": [
        "university life",
        "academic writing",
        "research vocabulary",
        "lecture terms",
        "library and study",
    ],
    "work": [
        "office communication",
        "business email",
        "meetings and presentations",
        "professional titles",
        "workplace phrases",
    ],
    "travel": [
        "airport and transit",
        "hotel and accommodation",
        "restaurant and food",
        "directions and transport",
        "shopping and money",
    ],
    "conversation": [
        "everyday small talk",
        "emotions and feelings",
        "hobbies and free time",
        "family and relationships",
        "weather and seasons",
    ],
    "general": [
        "everyday small talk",
        "emotions and feelings",
        "hobbies and free time",
        "family and relationships",
        "weather and seasons",
    ],
}


def build_topic_vocab_prompt(
    level: str,
    goal: str,
    target_lang: str,
    native_lang: str,
    recent_topics: list[str],
    count: int = 8,
    force_topic: str | None = None,
) -> str:
    name = lang_name(target_lang)
    native_name = lang_name(native_lang)

    _card_str = "card" if count == 1 else "cards"

    card_instructions = (
        f"For each word, call create_flash_card with:\n"
        f"  - word: the {name} word/phrase\n"
        f"  - translation: {native_name} translation\n"
        f"  - example_sentence: a natural {name} sentence using the word\n"
        f"  - word_type: noun/verb/adjective/phrase\n"
        f"Level filter — STRICT: only include words at {level} or above.\n"
        f"EXCLUDE any word a beginner would know: greetings, numbers, basic nouns (Haus, Buch, Auto), "
        f"simple verbs (gehen, haben, sein), very common words (Prüfung, Vorlesung, Arbeit, Büro). "
        f"If you're unsure whether a word is too basic — skip it and pick a more specific, less common word.\n"
        f"Prefer: multi-word phrases, collocations, formal register words, discipline-specific terms.\n"
    )

    if force_topic:
        return (
            f"You are generating vocabulary flashcards for a {name} learner.\n"
            f"Level: {level}. Goal: {goal}. Native language: {native_name}.\n\n"
            f"Generate exactly {count} high-frequency, useful {name} words or phrases"
            f" for the topic: '{force_topic}'.\n"
            f"{card_instructions}"
            f"Start your response with exactly: 'Topic: {force_topic}' then create the {_card_str}."
            f" No other text."
        )

    topics = GOAL_TOPICS.get(goal, GOAL_TOPICS["general"])
    avoid = ", ".join(recent_topics) if recent_topics else "none"
    topic_list = ", ".join(f'"{t}"' for t in topics)
    return (
        f"You are generating vocabulary flashcards for a {name} learner.\n"
        f"Level: {level}. Goal: {goal}. Native language: {native_name}.\n\n"
        f"Available topics for this goal: {topic_list}\n"
        f"Recently used topics (avoid these): {avoid}\n\n"
        f"Pick ONE topic from the available list that has NOT been recently used.\n"
        f"Generate exactly {count} high-frequency, useful {name} words or phrases for that topic.\n"
        f"{card_instructions}"
        f"Start your response with exactly: 'Topic: [chosen topic name]' then create the {_card_str}."
        f" No other text."
    )


def build_writing_task_prompt(
    article_text: str, target_lang: str, level: str, mode: str = "sentences"
) -> str:
    name = lang_name(target_lang)
    article_excerpt = article_text[:800]

    if mode == "sentences":
        return (
            f"Based on this {name} article excerpt, give the student a short writing task.\n\n"
            f"Article:\n{article_excerpt}\n\n"
            f"Student level: {level}\n\n"
            f"Pick 2–3 interesting or level-appropriate words from the article. "
            f"Ask the student to write 2–3 sentences using those words. "
            f"Be specific: name the exact words and what context to write about. "
            f"Reply ONLY with the writing task instructions, nothing else."
        )

    if mode == "grammar":
        return (
            f"Based on this {name} article excerpt, design a grammar-focused writing task.\n\n"
            f"Article:\n{article_excerpt}\n\n"
            f"Student level: {level}\n\n"
            f"Pick ONE grammar structure that appears naturally in the article and is appropriate for {level} "
            f"(e.g. Konjunktiv II, Passiv, Relativsätze, Modalverben, Genitive, indirect speech). "
            f"Ask the student to write 3–5 sentences using that structure, inspired by the article topic. "
            f"Name the grammar structure clearly and give a brief example. "
            f"Reply ONLY with the task instructions, nothing else."
        )

    if mode == "article":
        return (
            f"Based on this {name} article excerpt, design an extended writing task for exam preparation.\n\n"
            f"Article:\n{article_excerpt}\n\n"
            f"Student level: {level}\n\n"
            f"Create a task that requires the student to write a structured text of 200–250 words in {name}. "
            f"The task should resemble the EPD (Ergänzungsprüfung Deutsch) exam format used in Austria: "
            f"a formal or semi-formal text (Stellungnahme, Erörterung, or Kommentar) on a topic related to the article. "
            f"Specify: the text type, the topic/prompt, and 2–3 points the student should address. "
            f"Reply ONLY with the task instructions, nothing else."
        )

    return build_writing_task_prompt(article_text, target_lang, level, mode="sentences")


def build_writing_review_prompt(
    writing_task: str,
    user_writing: str,
    level: str,
    native_lang: str,
    target_lang: str,
    mode: str = "sentences",
) -> str:
    name = lang_name(target_lang)
    native_name = lang_name(native_lang)
    base = (
        f"Review this {name} writing exercise. Student level: {level}. Native: {native_name}.\n\n"
        f"Task given: {writing_task}\n\n"
        f"Student wrote:\n{user_writing}\n\n"
    )

    if mode == "sentences":
        return base + (
            f"Instructions:\n"
            f"1. Correct all grammar and vocabulary mistakes. Show each correction in {name} and {native_name}.\n"
            f"2. Highlight 1–2 words/phrases that are especially natural or worth remembering.\n"
            f"3. One sentence of encouragement.\n"
            f"4. Create flashcards for mistakes + highlighted vocabulary. Max 5 cards.\n"
            f"   Only create cards if the student made a genuine attempt.\n"
        )

    if mode == "grammar":
        return base + (
            f"Instructions:\n"
            f"1. Check specifically whether the target grammar structure was used correctly. "
            f"Point out every grammatical error in the structure with a correction in {name} and {native_name}.\n"
            f"2. Also correct any other grammar or vocabulary mistakes.\n"
            f"3. Show 1 example of the same structure used beautifully.\n"
            f"4. One sentence of encouragement.\n"
            f"5. Create flashcards for grammar mistakes (use the corrected form as the card). Max 5 cards.\n"
            f"   Only create cards if the student made a genuine attempt.\n"
        )

    if mode == "article":
        return base + (
            f"Instructions (Essay exam preparation feedback):\n"
            f"1. Structure: Does the text have a clear introduction, body, and conclusion? Comment on this.\n"
            f"2. Content: Did the student address the required points from the task? What's missing or shallow?\n"
            f"3. Language: Correct all grammar mistakes. Note vocabulary that is too simple for {level} "
            f"and suggest more formal/precise alternatives.\n"
            f"4. Cohesion: Comment on connectors, transitions, and register (formal/informal).\n"
            f"5. Overall grade estimate: A (sehr gut) / B (gut) / C (befriedigend) / D (needs work), with one sentence why.\n"
            f"6. Create flashcards for: vocabulary gaps, formal alternatives the student should know. Max 5 cards.\n"
            f"   Only create cards if the student made a genuine attempt.\n"
            f"Write feedback in {name}, show corrections also in {native_name}.\n"
        )

    return build_writing_review_prompt(
        writing_task, user_writing, level, native_lang, target_lang, mode="sentences"
    )


def build_word_capture_prompt(
    word: str, target_lang: str, native_lang: str, context: str | None = None
) -> str:
    name = lang_name(target_lang)
    native_name = lang_name(native_lang)
    context_hint = (
        f"\nContext hint from the user: '{context}'. Use this to pick the correct meaning or register."
        if context
        else ""
    )
    return (
        f"The student is learning {name} and wants to add '{word}' to their flashcard deck."
        f"{context_hint}\n\n"
        f"Respond with ONLY a JSON object (no markdown, no code fences, no extra text) with these fields:\n"
        f"  word: the {name} word exactly as given\n"
        f"  article: grammatical article if noun (e.g. der/die/das for German, el/la for Spanish) — null if not a noun\n"
        f"  word_type: one of noun / verb / adjective / phrase\n"
        f"  translation: {native_name} translation\n"
        f"  example_sentence: one natural {name} sentence using the word\n"
        f"  grammar_note: one short note useful for learners "
        f"(e.g. plural form for nouns, key conjugation for verbs) written in {native_name}. Max 1 sentence.\n\n"
        f'Example for "Brot" (German \u2192 English):\n'
        f'{{"word":"Brot","article":"das","word_type":"noun","translation":"bread",'
        f'"example_sentence":"Ich esse jeden Morgen frisches Brot.",'
        f'"grammar_note":"Plural: die Brote"}}\n\n'
        f"Now generate the JSON for '{word}'."
    )


def build_review_prompt(
    article_text: str,
    questions: list[str],
    answers: list[str],
    level: str,
    native_lang: str,
    target_lang: str,
) -> str:
    name = lang_name(target_lang)
    native_name = lang_name(native_lang)
    qa_pairs = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(questions, answers, strict=False))
    return f"""
Review these {name} comprehension answers. Student level: {level}. Native language: {native_name}.

Article:
{article_text}

Questions and answers:
{qa_pairs}

Instructions:
1. Be HONEST and CRITICAL. If an answer is incomplete, vague, or missing key details from the article — say so explicitly.
2. Point out every grammar or vocabulary mistake with a correction.
3. If an answer is simply wrong, explain the correct answer using the article.
4. Write feedback in {name}. Show corrections also in {native_name} so the student understands.

Do NOT be overly positive if the answers are incomplete. The student should know exactly what they missed.
Do NOT create flashcards — this is comprehension feedback only.
""".strip()
