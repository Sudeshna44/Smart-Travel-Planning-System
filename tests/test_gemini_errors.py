from travel_planner import create_travel_crew, gemini_failure_guidance


def test_gemini_quota_error_shows_specific_guidance_without_raw_response():
    title, guidance = gemini_failure_guidance(
        Exception("429 RESOURCE_EXHAUSTED quota private-provider-metadata")
    )

    assert title == "The Gemini API quota or rate limit was reached."
    assert "Wait for the quota to reset" in guidance
    assert "private-provider-metadata" not in title + guidance


def test_other_errors_show_google_configuration_guidance():
    title, guidance = gemini_failure_guidance(Exception("connection failed"))

    assert "could not be completed" in title
    assert "Google AI Studio API key" in guidance


def test_crew_uses_gemini_model_with_supplied_key():
    crew = create_travel_crew(
        api_key="test-key",
        model="gemini-3-flash-preview",
        trip={},
        research={},
        budget={},
        alternative={},
    )

    assert crew.agents[0].llm.model == "gemini-3-flash-preview"
    assert crew.agents[0].llm.provider == "gemini"
