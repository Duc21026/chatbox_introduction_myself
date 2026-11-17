from backend import source_store


def test_canonical_source_is_in_data_directory():
    config = source_store.default_config()
    assert config.source_path.endswith("/data/chatbot.txt")
    assert config.courses_path.endswith("/data/sources/courses.csv")
    assert config.aliases_path.endswith("/data/sources/aliases.txt")
