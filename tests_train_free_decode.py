import unittest

from scripts.build_dataset import select_train_free_decode_pools


class TrainFreeDecodePoolTests(unittest.TestCase):
    def test_separates_real_and_synth_and_requires_tast(self):
        utts = [
            {"utt_id": "n1", "kind": "nasap", "domain": "real"},
            {"utt_id": "n2", "kind": "nasap", "domain": "real"},
            {"utt_id": "p1", "kind": "pdmx", "domain": "synth"},
            {"utt_id": "m1", "kind": "maestro", "domain": "real"},
        ]
        labels = {
            "n1": {"TAST": "|4/4k0 <|0.00|>"},
            "n2": {"A2S": "|4/4k0"},
            "p1": {"TAST": "|4/4k0 <|0.00|>"},
            "m1": {"TAST": "|4/4k0 <|0.00|>"},
        }

        pools = select_train_free_decode_pools(utts, labels)

        self.assertEqual([u["utt_id"] for u in pools["nasap_real_tast"]], ["n1"])
        self.assertEqual([u["utt_id"] for u in pools["pdmx_synth_tast"]], ["p1"])


if __name__ == "__main__":
    unittest.main()
