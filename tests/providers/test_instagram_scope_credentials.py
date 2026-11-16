from django import forms
from django.test import SimpleTestCase

from apps.credentials.forms import PlatformCredentialAdminForm


class InstagramScopeCredentialTests(SimpleTestCase):
    def clean(self, value):
        form = PlatformCredentialAdminForm()
        form.cleaned_data = {"credentials": value}
        return form.clean_credentials()

    def test_scope_array_and_secret_survive_admin_cleaning(self):
        scopes = ["instagram_shopping_tag_products", "instagram_branded_content_creator", "business_management"]
        result = self.clean({"client_id": "fixture", "client_secret": "fixture-secret", "additional_instagram_scopes": scopes})
        self.assertEqual(result["additional_instagram_scopes"], scopes)
        self.assertEqual(result["client_secret"], "fixture-secret")

    def test_invalid_scope_values_are_rejected(self):
        for value in ["['business_management']", ["ads_management"], {}, [None]]:
            with self.subTest(value=value), self.assertRaises(forms.ValidationError):
                self.clean({"additional_instagram_scopes": value})
