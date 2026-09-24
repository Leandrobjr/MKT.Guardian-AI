import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_orchestrator import CampaignOrchestrator


class TestCampaignOrchestratorFlow(unittest.TestCase):
    def test_desktop_nao_bloqueia_worker_em_input_de_historia(self):
        orchestrator = CampaignOrchestrator.__new__(CampaignOrchestrator)
        original = os.environ.get("STORY_APPROVAL")
        os.environ["STORY_APPROVAL"] = "true"
        try:
            self.assertFalse(
                orchestrator._story_approval_enabled({"aprovacao_desktop": True})
            )
            self.assertTrue(
                orchestrator._story_approval_enabled({"aprovacao_terminal": True})
            )
        finally:
            if original is None:
                os.environ.pop("STORY_APPROVAL", None)
            else:
                os.environ["STORY_APPROVAL"] = original


if __name__ == "__main__":
    unittest.main()
