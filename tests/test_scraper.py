'''
Test module for the LiveTrailScraper class
'''
import unittest
import pytest
import inspect
from scraper.scraper import LiveTrailScraper
import pandas as pd

# Define a function to get all functions defined in a module
def get_functions(module):
    return inspect.getmembers(module, inspect.isfunction)

# Define a function to get all methods defined in a test class
def get_test_methods(test_class) -> list[str]:
    return [method[5:] for method in dir(test_class) if callable(getattr(test_class, method)) and method.startswith("test")]

# Define a function to get unused functions
def get_unused_functions(module, test_class) -> set[str]:
    module_functions = set(name for name, _ in get_functions(module))
    test_methods = set(get_test_methods(test_class))
    untested_methods = module_functions - test_methods
    # remove internal class methods (they are tested indirectlyu via the exposed methods)
    exceptions_test_methods = set(list(filter(lambda x: not x.startswith('_'), untested_methods)))
    return exceptions_test_methods

class TestLiveTrailScraper(unittest.TestCase):
    # Test case for _checkEventYear method
    def test_check_event_valid(self):
        scraper = LiveTrailScraper()
        with pytest.raises(ValueError):
            scraper._check_event_year("invalid_event", "2022")

    # Test case for _checkEventYear method
    def test_check_event_year(self):
        scraper = LiveTrailScraper()
        with pytest.raises(ValueError):
            scraper._check_event_year("transgrancanaria", "1995")

    # Test case for setYears and _checkEventYear method
    def test__is_valid_year(self):
        scraper = LiveTrailScraper()
        with pytest.raises(ValueError):
            scraper.set_years(["1995", "abc", "2023"])

    # Test case for setYears method
    def test_set_years(self):
        scraper = LiveTrailScraper()
        scraper.set_years(["2015", "2023"])
        assert scraper.years == ["2015", "2023"]
    
    def test_set_events(self):
        scraper = LiveTrailScraper()
        events = ['transgrancanaria', 'penyagolosa', 'utmb']
        scraper.set_events(events)
        self.assertEqual(scraper.events, events)
        
    def test_set_race(self):
        scraper = LiveTrailScraper()
        events = ['penyagolosa']
        scraper.set_events(events)
        race = 'mim'
        scraper.set_race(race)
        self.assertEqual(scraper.race, race)

    # Test case for getControlPoints and _parseControlPoints method
    def test_get_control_points(self):
        # Transgrancanaria 2023 data
        control_points = {
                            'Salida Clasic': (0.0, 0, 0),
                            'Tenoya': (11.43, 348, -188),
                            'Arucas': (19.44, 704, -482),
                            'Teror': (31.95, 1509, -922),
                            'Fontanales': (43.55, 2463, -1461),
                            'El Hornillo': (53.51, 3089, -2339),
                            'Artenara': (67.11, 4156, -2961),
                            'Tejeda': (79.63, 4919, -3878),
                            'Roque Nublo': (88.15, 5869, -4128),
                            'Garañon': (91.32, 6042, -4372),
                            'Tunte': (104.26, 6369, -5483),
                            'Ayagaures': (116.57, 6803, -6500),
                            'Meta Parque Sur': (130.74, 7000, -6970)
                        }
        scraper = LiveTrailScraper(events=["transgrancanaria"], years=["2023"])
        cp = scraper.get_control_points()['classic']
        assert cp == control_points

        # Sainté-Lyon 2021 data
        control_points = {  
                            'Saint Etienne': (0.0, 0, 0),
                            'Saint-Christo-en-Jarez': (18.14, 602, -338),
                            'Sainte-Catherine': (31.96, 1109, -908),
                            'Le Camp - Saint-Genou': (45.01, 1522, -1396),
                            'Soucieu-en-Jarrest': (55.86, 1736, -1863),
                            'Chaponost': (65.38, 1857, -2041),
                            'Lyon': (78.3, 2126, -2448)
                        }
        scraper = LiveTrailScraper(events=["saintelyon"], years=["2021"])
        cp = scraper.get_control_points()['78km']
        assert cp == control_points

    # Test case for downloadData method
    def test_download_data(self):
        scraper = LiveTrailScraper(events=["transgrancanaria"], years=["2023"])
        scraper.download_data()
        results_raw = pd.read_csv('data/transgrancanaria/transgrancanaria_classic_2023.csv', sep=',')
        data = {
            'n': 4,
            'doss': 18,
            'nom': 'BUTACI',
            'prenom': 'Raul',
            'cat': 'MA30H',
            '00': '00:00:13',
            '21': '00:49:34',
            '23': '01:33:48',
            '25': '02:49:13',
            '27': '04:10:40',
            '29': '05:19:47',
            '31': '06:58:30',
            '33': '08:27:01',
            '35': '09:51:18',
            '41': '10:16:20',
            '43': '11:35:38',
            '45': '12:54:03',
            '110': '14:15:53'
        }
        assert pd.Series(data, name='3').equals(results_raw.iloc[3])

    # Test case for getEvents method
    def test_get_events(self):
        scraper = LiveTrailScraper()
        # On 10/02/2024 there are 323 events
        assert len(scraper.get_events()) > 322

    # Test case for getEventsYears method
    def test_get_events_years(self):
        evs = LiveTrailScraper().get_events_years()
        # On 10/02/2024 there are 3034 of tuples event,year
        assert sum([len(e) for e in evs]) > 3033

    # Test case for getRaces method
    def test_get_races(self):
        data = {'transgrancanaria':
            {'2023':
                {'classic': 'Classic 128 KM',
                 'advance': 'Advanced 84 KM',
                 'maraton': 'Maraton 45 KM',
                 'starter': 'Starter 24 KM',
                 'promo': 'Promo',
                 'youth': 'Youth',
                 'family': 'Family'
                }
            }
        }
        races = LiveTrailScraper(events=["transgrancanaria"], years=["2023"]).get_races()
        assert data == races    

    # Test case for getData method
    def test_get_data(self):
        data = {
            'n': 4,
            'doss': 18,
            'nom': 'BUTACI',
            'prenom': 'Raul',
            'cat': 'MA30H',
            '00': '00:00:13',
            '21': '00:49:34',
            '23': '01:33:48',
            '25': '02:49:13',
            '27': '04:10:40',
            '29': '05:19:47',
            '31': '06:58:30',
            '33': '08:27:01',
            '35': '09:51:18',
            '41': '10:16:20',
            '43': '11:35:38',
            '45': '12:54:03',
            '110': '14:15:53'
        }
        
        scr = LiveTrailScraper(events=["transgrancanaria"], years=["2023"])
        assert pd.Series(data, name='3').equals(scr.get_data('classic').iloc[3])

    # Test case for getRaceInfo method
    def test_get_race_info(self):
        race_info = {'date': '2024-02-24', 'tz': '0', 'hd': '00:00:03', 'jd': '6'}
        # We pop 'tz' since it returns actual timezone, not event's so it changes over time and may fail
        race_info.pop('tz')
        scr = LiveTrailScraper(events=["transgrancanaria"], years=["2024"])
        scr_race_info = scr.get_race_info(bibN=20)
        scr_race_info.pop('tz')
        sorted_dict1 = sorted(race_info.items())
        sorted_dict2 = sorted(scr_race_info.items())
        assert sorted_dict1 == sorted_dict2, "Race info method Failed"

    def test__parce_race_info(self):
        xml_content='''
            <?xml version="1.0" encoding="UTF-8"?>
            <?xml-stylesheet type="text/xsl" href="coureur.xsl.php"?><d rech="20"><courses><c id="classic" n="Classic 126 KM" nc="Classic 126 KM" /><c id="advance" n="Advanced 84 KM" nc="Advanced 84 KM" /><c id="maraton" n="Maraton 46 KM" nc="Maraton 46 KM" /><c id="starter" n="Starter 21 KM" nc="Starter 21 KM" /><c id="promo" n="Promo" nc="Promo" /><c id="youth" n="Youth" nc="Youth" /><c id="family" n="Family" nc="Family" /><c id="kv" n="KV El Gigante" nc="KV El Gigante" /></courses>		  <fiche doss="20" c="classic" finishc="1"  dipl="1">
                                    <identite nom="BUTACI"
                        prenom="Raul"			  cat="MA30H"
                        sx="H"
                        descat="30-39"
                        club="Team BigK"			  			  			  
                                        nat="Rumania"
                            cio="ROU" a2="RO" a3="ROU" 			  			  				  				  ville="Tornabous" pays=""
                                                            />
                        <antecedents></antecedents>												<divers2></divers2>																																										<state code="f" clt="1"  cltcat="1" cltsx="1" />			<prev >
                                    </prev>
                                    <pass>
                        <e idpt="0" date="2024-02-24" tz="1" hd="00:00:03" jd="6" tps="00:00:00"  clt="-" tn="0" tnd="0" ></e><e idpt="21" ha="00:51:00" ja="6" tps="00:50:57" tn="0.84916666666667" tnd="0.84916666666667" tnp="0.84916666666667" clt="10" ></e><e idpt="23" ha="01:34:32" ja="6" tps="01:34:29" tn="1.5747222222222" tnd="1.5747222222222" tnp="0.72555555555556" clt="11" ></e><e idpt="25" ha="02:48:34" ja="6" tps="02:48:31" tn="2.8086111111111" tnd="2.8086111111111" tnp="1.2338888888889" clt="11" ></e><e idpt="27" ha="04:08:46" ja="6" tps="04:08:43" tn="4.1452777777778" tnd="4.1452777777778" tnp="1.3366666666667" clt="7" ></e><e idpt="29" ha="05:16:31" ja="6" tps="05:16:28" tn="5.2744444444444" tnd="5.2744444444444" tnp="1.1291666666667" clt="6" ></e><e idpt="31" ha="06:54:02" ja="6" tps="06:53:59" tn="6.8997222222222" tnd="6.8997222222222" tnp="1.6252777777778" clt="4" ></e><e idpt="33" ha="08:16:32" ja="6" tps="08:16:29" tn="8.2747222222222" tnd="8.3016666666667" tnp="1.375" clt="1" ></e><e idpt="35" ha="09:34:59" ja="6" tps="09:34:56" tn="9.5822222222222" tnd="9.5822222222222" tnp="1.2805555555556" clt="1" ></e><e idpt="41" ha="09:57:40" ja="6" tps="09:57:37" tn="9.9602777777778" tnd="9.9602777777778" tnp="0.37805555555556" clt="1" ></e><e idpt="43" ha="10:55:10" ja="6" tps="10:55:07" tn="10.918611111111" tnd="10.918611111111" tnp="0.95833333333333" clt="1" ></e><e idpt="45" ha="12:08:38" ja="6" tps="12:08:35" tn="12.143055555556" tnd="12.143055555556" tnp="1.2244444444444" clt="1" ></e><e idpt="110" ha="13:22:35" ja="6" tps="13:22:32" tn="13.375555555556" tnd="16.064166666667" tnp="1.2325" clt="1" ></e>		  </pass>
                    
                    
                            
                    
                    <pts><pt idpt="0" n="Las Palmas" nc="Salida Cla" km="0" d="0" a="1" x="50" y="166" px="6" py="83" lon="-15.43111" lat="28.14806" meet="1" /><pt idpt="21" n="Tenoya" nc="Tenoya" km="11.08" d="341" a="161" x="119" y="155" px="14" py="78" lon="-15.49115" lat="28.11901" meet="1" /><pt idpt="23" n="Barreto" nc="Barreto" km="18.86" d="693" a="223" x="167" y="151" px="20" py="76" lon="-15.51919" lat="28.11369" meet="1" /><pt idpt="25" n="Teror" nc="Teror" km="31" d="1491" a="588" x="243" y="126" px="29" py="63" lon="-15.54791" lat="28.05854" meet="1" /><pt idpt="27" n="Fontanales" nc="Fontanales" km="42.28" d="2402" a="1003" x="313" y="98" px="37" py="49" lon="-15.60705" lat="28.05671" meet="1" /><pt idpt="29" n="El Hornillo" nc="El Hornill" km="51.97" d="3010" a="751" x="373" y="115" px="44" py="58" lon="-15.66071" lat="28.05609" meet="1" /><pt idpt="31" n="Artenara" nc="Artenara" km="65.2" d="4061" a="1196" x="456" y="85" px="54" py="43" lon="-15.65112" lat="28.02207" meet="1" /><pt idpt="33" n="Tejeda" nc="Tejeda" km="77.36" d="4799" a="1042" x="531" y="96" px="62" py="48" lon="-15.61532" lat="27.99573" meet="1" /><pt idpt="35" n="Roque Nublo" nc="Roque Nubl" km="85.63" d="5711" a="1742" x="583" y="48" px="69" py="24" lon="-15.61235" lat="27.97014" meet="1" /><pt idpt="41" n="Garañon" nc="Garañon" km="88.72" d="5888" a="1671" x="602" y="53" px="71" py="27" lon="-15.58802" lat="27.96869" meet="1" /><pt idpt="43" n="Tunte" nc="Tunte" km="101.28" d="6191" a="887" x="680" y="106" px="80" py="53" lon="-15.57303" lat="27.92521" meet="1" /><pt idpt="45" n="Ayagaures" nc="Ayagaures" km="113.23" d="6593" a="304" x="754" y="146" px="89" py="73" lon="-15.60726" lat="27.85125" meet="1" /><pt idpt="110" n="Meta Parque Sur" nc="Meta Parqu" km="126.98" d="6792" a="31" x="840" y="164" px="99" py="82" lon="-15.59686" lat="27.76360" meet="1" /></pts>		  		</fiche></d>
            '''
        race_info = {'date': '2024-02-24', 'tz': '1', 'hd': '00:00:03', 'jd': '6'}
        scr = LiveTrailScraper()
        scr_race_info = scr._parse_race_info(xml_content)
        sorted_dict1 = sorted(race_info.items())
        sorted_dict2 = sorted(scr_race_info.items())
        assert sorted_dict1 == sorted_dict2, "Race info method Failed"

    def test_get_random_runner_bib(self):
        bibs = {'2024':
                {'classic': '20',
                 'advance': '1002',
                 'maraton': '2057',
                 'starter': '4001',
                 'promo': '5074',
                 'youth': '5553',
                 'family': '10612'
                 }
             }
        scr = LiveTrailScraper(events=["transgrancanaria"], years=["2024"])
        scr_bibs = scr.get_random_runner_bib()
        sorted_dict1 = sorted(bibs["2024"].items())
        assert "2024" in scr_bibs, "Get random runner bib method Failed"
        sorted_dict2 = sorted(scr_bibs["2024"].items())
        assert sorted_dict1 == sorted_dict2, "Get random runner bib method Failed"

    def test_set_race(self):
        # TODO
        assert 0==0

    def test_set_events(self):
        # TODO
        assert 0==0

    def test_get_races_physical_details(self):
        race_details = {
            'classic': {'distance': 126.98, 'elevation_pos': 6792, 'elevation_neg': -6762},
            'advance': {'distance': 84.65, 'elevation_pos': 4996, 'elevation_neg': -4967},
            'maraton': {'distance': 46.75, 'elevation_pos': 1914, 'elevation_neg': -2930},
            'starter': {'distance': 22.45, 'elevation_pos': 1448, 'elevation_neg': -1287},
            'promo': {'distance': 12.16, 'elevation_pos': 736, 'elevation_neg': -921},
            'youth': {'distance': 12.16, 'elevation_pos': 736, 'elevation_neg': -921},
            'family': {'distance': 12.16, 'elevation_pos': 736, 'elevation_neg': -921},
            'kv': {'distance': 5.66, 'elevation_pos': 1146, 'elevation_neg': -136}
            }
        race_details = {
            key: dict(sorted(value.items()))
            for key, value in race_details.items()
        }
        scr = LiveTrailScraper(events=["transgrancanaria"], years=["2024"])
        scr_race_details = scr.get_races_physical_details()
        scr_race_details = {
            key: dict(sorted(value.items()))
            for key, value in scr_race_details.items()
        }

        assert race_details == scr_race_details, "get_races_physical_details test failed"

    def test_implemented_tests(self):
        unused_functions = get_unused_functions(LiveTrailScraper, TestLiveTrailScraper)
        print(unused_functions)
        assert len(unused_functions) == 0, "LiveTrailScraper is not tested enough. pytest -s for details."
