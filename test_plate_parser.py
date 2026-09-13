import unittest
from plate_parser import parse_plate

class PlateParserTests(unittest.TestCase):
    def test_private(self):
        self.assertEqual(parse_plate("21ص345ایران20"),
            {"plate":"21ص345ایران20","category":"private","province_code":"21",
             "serial":"345","letter":"ص","region_code":"20"})
    def test_standard_categories(self):
        for text, cat in {"12ت34520":"taxi","12ع34520":"public",
            "12ک34520":"agricultural","12الف34520":"government",
            "12گ34520":"temporary","12پ34520":"police","12ث34520":"sepah",
            "12ز34520":"defence_ministry","12ش34520":"army",
            "12ف34520":"armed_forces_staff","12ژ34520":"disabled_veteran"}.items():
            self.assertEqual(parse_plate(text)["category"], cat)
    def test_motorcycle(self):
        p = parse_plate("۱۲۳۴۵۶۷۸")
        self.assertEqual((p["category"],p["province_code"],p["serial"]),
                         ("motorcycle","123","45678"))
    def test_unknown(self):
        p = parse_plate("21?345ایران20")
        self.assertEqual((p["province_code"],p["letter"],p["serial"],p["region_code"]),
                         ("21","?","345","20"))
    def test_color_fallback(self):
        self.assertEqual(parse_plate("12?34520","yellow",False)["category"],
                         "public_or_service")

if __name__ == "__main__":
    unittest.main()
