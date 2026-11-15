from urllib.parse import parse_qs, urlparse

import pytest

from providers.instagram import InstagramProvider


def test_existing_connections_keep_the_six_default_scopes():
    provider = InstagramProvider({"client_id": "fixture", "client_secret": "fixture"})
    assert len(provider.required_scopes) == 6
    assert "business_management" not in provider.required_scopes
    assert "instagram_shopping_tag_products" not in provider.required_scopes


def test_explicit_opt_in_is_bound_to_the_generated_oauth_url():
    extra = ["instagram_shopping_tag_products", "instagram_branded_content_creator", "business_management"]
    provider = InstagramProvider(
        {"client_id": "fixture", "client_secret": "fixture", "additional_instagram_scopes": extra + extra}
    )
    url = provider.get_auth_url("https://studio.pragsys.io/social-accounts/callback/instagram/", "fixture-state")
    query = parse_qs(urlparse(url).query)
    assert len(query["scope"][0].split(",")) == 9
    assert set(extra) <= set(query["scope"][0].split(","))
    assert "ads_management" not in query["scope"][0]
    assert query["state"] == ["fixture-state"]


@pytest.mark.parametrize("value", ["business_management", ["ads_management"], [None], {"scope": "business_management"}])
def test_no_arbitrary_permission_forwarding(value):
    provider = InstagramProvider(
        {"client_id": "fixture", "client_secret": "fixture", "additional_instagram_scopes": value}
    )
    with pytest.raises(ValueError, match="Unrecognized"):
        provider.get_auth_url("https://example.org/callback", "fixture-state")
