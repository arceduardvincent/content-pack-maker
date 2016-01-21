import logging
import os

import vcr
from hypothesis import assume, given
from hypothesis.strategies import integers, lists, sampled_from, sets, text, \
    tuples

from contentpacks.khanacademy import _combine_catalogs, _get_video_ids, \
    retrieve_dubbed_video_mapping, retrieve_html_exercises, \
    retrieve_kalite_data, retrieve_translations, retrieve_subtitles
from contentpacks.utils import NODE_FIELDS_TO_TRANSLATE, translate_nodes, Catalog


logging.basicConfig()
logging.getLogger("vcr").setLevel(logging.DEBUG)

class Test_retrieve_subtitles:
    def test_incorrect_youtube_id(self):
        incorrect_list = ["aaa"]
        empty_list = retrieve_subtitles(incorrect_list, force=True)
        test_list = []
        assert not empty_list
        assert isinstance(empty_list, list)

    def test_correct_youtube_id(self):
        correct_list = ["y2-uaPiyoxc"]
        filled_list = retrieve_subtitles(correct_list, force=True)
        test_list = ["y2-uaPiyoxc"]
        assert filled_list
        assert isinstance(filled_list, list)

    def test_correct_and_incorrect_youtube_id(self):
        mixed_list =  ["y2-uaPiyoxc", "asdadsafa"]
        filled_list = retrieve_subtitles(mixed_list, force=True)
        test_list = ["y2-uaPiyoxc"]
        assert filled_list
        assert isinstance(filled_list, list)
        assert filled_list == test_list

    def test_directory_made(self):
        correct_list = ["y2-uaPiyoxc"]
        youtube_id = correct_list[0]
        file_suffix = '.vtt'
        retrieve_subtitles(correct_list, force=True)
        path = os.getcwd() + "/build/subtitles/en/" + youtube_id + file_suffix
        assert os.path.exists(path)

    def test_correct_youtube_id_and_incorrect_langpack(self):
        correct_list = ["y2-uaPiyoxc"]
        empty_list = retrieve_subtitles(correct_list,"falselang", force=True)
        test_list = []
        assert not empty_list
        assert isinstance(empty_list, list)

class Test_retrieve_translations:

    # Note, the CrowdIn request below has been cached by vcr, avoiding
    # the need for the crowdin key. If you do delete the file below,
    # then you need the key in your environment to successfully make
    # the request.
    @vcr.use_cassette("tests/fixtures/cassettes/crowdin/kalite/es.zip.yml")
    def test_returns_list_of_po_files(self):
        project_id = "ka-lite"
        project_key = "dummy"
        catalog = retrieve_translations(project_id, project_key)

        assert isinstance(catalog, Catalog)


class Test__combine_catalogs:

    @given(text(), integers(), integers())
    def test_total_message_count(self, txt, msgcount1, msgcount2):
        assume(0 < msgcount1 <= msgcount2 <= 100)

        catalog1 = Catalog()
        for n in range(msgcount1):
            catalog1.add(id=str(n), string=txt)

        catalog2 = Catalog()
        for n in range(msgcount2):
            catalog2.add(id=str(n + 1000), string=txt)  # we add 1000 to make sure the ids are unique

        newcatalog = _combine_catalogs(catalog1, catalog2)

        # the +1 is to account for the empty message, which gets added automatically.
        assert len(list(newcatalog)) == msgcount1 + msgcount2 + 1


class Test__get_video_ids:

    @given(lists(tuples(text(min_size=1), sampled_from(["Exercise", "Video", "Topic"]))))
    def test_given_list_returns_only_videos(self, contents):
        contents = [{"kind": kind, "id": id} for id, kind in contents]
        video_count = len([node for node in contents if node.get("kind") == "Video"])

        assert len(_get_video_ids(contents)) == video_count

    @vcr.use_cassette("tests/fixtures/cassettes/kalite/node_data.json.yml")
    def test_returns_something_in_production_json(self):
        """
        Since we know that test_given_list_returns_only_videos works, then
        we only need to check that we return something for the actual contents.json
        to make sure we're reading the right attributes.
        """
        data = retrieve_kalite_data()

        assert _get_video_ids(data)


class Test_retrieve_kalite_data:

    @vcr.use_cassette("tests/fixtures/cassettes/kalite/node_data.json.yml")
    def test_returns_dict(self):
        data = retrieve_kalite_data()
        assert isinstance(data, list)


@vcr.use_cassette("tests/fixtures/cassettes/kalite/node_data.json.yml")
def _get_all_video_ids():
    """
    Test utility function so we only need to generate the list of video
    ids once, and then assign that to an instance variable. We
    wrap it as a function instead of assigning the value of
    retrieve_kalite_content_data directly so we can use the
    cassette system to cache the results, avoiding an expensive
    http request.

    """
    content_data = retrieve_kalite_data()

    ids = _get_video_ids(content_data)

    # return a tuple, to make sure it gets never modified.
    ids_tuple = tuple(ids)

    # just take the first 10 ids -- don't run too many
    return ids_tuple[:10]


class Test_retrieve_dubbed_video_mapping:

    video_list = _get_all_video_ids()

    @vcr.use_cassette("tests/fixtures/cassettes/khanacademy/video_api.yml", record_mode="new_episodes")
    @given(sets(elements=sampled_from(video_list)))
    def test_returns_dict_given_singleton_list(self, video_ids):

        dubbed_videos_set = set(
            retrieve_dubbed_video_mapping(
                video_ids,
                lang="de"
            ))

        assert dubbed_videos_set.issubset(video_ids)


class Test_translating_kalite_data:

    @classmethod
    @vcr.use_cassette("tests/fixtures/cassettes/translate_exercises.yml", filter_query_parameters=["key"])
    def setup_class(cls):
        cls.ka_catalog = retrieve_translations("khanacademy", "dummy", lang_code="es-ES", includes="*learn.*.po")

    @vcr.use_cassette("tests/fixtures/cassettes/translate_topics.yml")
    def test_translate_nodes(self):
        node_data = retrieve_kalite_data()
        translated_node_data = translate_nodes(
            node_data,
            self.ka_catalog,
        )

        for translated_node, untranslated_node in zip(translated_node_data,
                                                    node_data):
            for field in NODE_FIELDS_TO_TRANSLATE:
                untranslated_fieldval = untranslated_node.get(field)
                translated_fieldval = translated_node.get(field)

                assert (translated_fieldval ==
                        self.ka_catalog.get(
                            untranslated_fieldval,
                            untranslated_fieldval)
                )


class Test_retrieve_html_exercises:

    @vcr.use_cassette("tests/fixtures/cassettes/test_retrieve_html_exercises_setup.yml")
    def setup(self):
        self.exercise_data = retrieve_kalite_data()
        self.khan_exercises = [e.get("id") for e in self.exercise_data if not e.get("uses_assessment_items")\
                               and e.get("kind") == "Exercise"]
        self.khan_exercises.sort()

    @vcr.use_cassette("tests/fixtures/cassettes/test_retrieve_html_exercises.yml")
    def test_creates_folder_with_contents(self):
        exercises = sorted(self.khan_exercises)[:5]  # use only first five for fast testing
        exercise_path, retrieved_exercises = retrieve_html_exercises(exercises, lang="es")

        assert retrieved_exercises  # not empty
        assert set(retrieved_exercises).issubset(self.khan_exercises)
        assert os.path.exists(exercise_path)

    @vcr.use_cassette("tests/fixtures/cassettes/test_retrieve_html_exercises_2.yml")
    def test_doesnt_return_exercises_without_translation(self):
        # The expected behaviour from KA's API is that it would return
        # the english version of an exercise if either a translated
        # exercise for the given language doesn't exist, or the
        # language is unsupported.
        exercise = self.khan_exercises[0]
        lang = "aaa"            # there's no language with code aaa... I hope?

        path, retrieved_exercises = retrieve_html_exercises([exercise], lang, force=True)

        assert not retrieved_exercises

    @vcr.use_cassette("tests/fixtures/cassettes/test_retrieve_html_exercises_3.yml")
    def test_returns_exercise_with_translation(self):
        # espanol has almost complete
        # translation. Assuming this specific
        # exercise has one
        lang = "es"
        exercise = self.khan_exercises[0]

        path, retrieved_exercises = retrieve_html_exercises([exercise], lang, force=True)

        assert retrieved_exercises == [exercise]
