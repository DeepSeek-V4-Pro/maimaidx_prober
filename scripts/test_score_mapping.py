"""双源谱面映射回归；只使用合成数据，不连接账号或写后端。"""
from pathlib import Path
from unittest.mock import AsyncMock
import runpy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
runpy.run_path(str(Path(__file__).with_name('quick_command_test.py')))
from core.services.music import MusicService  # noqa: E402
from core.services.normalize import normalize_lxns_bests  # noqa: E402
from core.services.player import PlayerQueryService  # noqa: E402

SONGS = [
    {'id': '123', 'title': 'Dual', 'type': 'SD', 'ds': [1, 2, 3, 4]},
    {'id': '10123', 'title': 'Dual', 'type': 'DX', 'ds': [5, 6, 7, 8]},
]

class MappingTests(unittest.IsolatedAsyncioTestCase):
    def music(self):
        music = MusicService(AsyncMock(), None, AsyncMock(), 300, 300)
        music.get_songs = AsyncMock(return_value=SONGS)
        music._get_lxns_cache = AsyncMock(return_value={})
        music._lxns_by_id = {123: {'id': 123, 'title': 'Dual'}}
        return music

    def player(self):
        p = PlayerQueryService.__new__(PlayerQueryService)
        p._music = self.music()
        p._bindings = AsyncMock()
        p._bindings.get.return_value = {'import_token': 'synthetic'}
        p._auth_svc = AsyncMock()
        p._auth_svc.get_auth.return_value = ({'X-User-Token': 'synthetic'}, '')
        p._df_oauth = None
        p._df = AsyncMock()
        p._df.get_player_records.return_value = {'records': []}
        p._df.update_records.return_value = {'message': 'ok'}
        p._lxns = AsyncMock()
        p._lxns.get_user_scores.return_value = {'data': []}
        p._lxns.upload_user_scores.return_value = {'success': True}
        return p

    async def test_dual_chart_index_and_ambiguity(self):
        m = self.music()
        self.assertEqual((await m.get_df_song_by_lxns_id(123, 'dx'))['id'], '10123')
        self.assertEqual((await m.get_df_song_by_lxns_id(123, 'standard'))['id'], '123')
        self.assertIsNone(await m.get_df_song_by_lxns_id(123))
        self.assertIsNone(await m.get_df_song_by_lxns_id(123, 'unknown'))

    async def test_cache_refresh(self):
        m = self.music()
        await m.get_df_song_by_lxns_id(123, 'dx')
        m.invalidate()
        m.get_songs.return_value = [SONGS[0]]
        self.assertIsNone(await m.get_df_song_by_lxns_id(123, 'dx'))

    def test_b50_groups_preserve_chart_type(self):
        result = normalize_lxns_bests({'standard': [{'type': 'dx'}], 'dx': [{'type': 'standard'}]})
        self.assertEqual(result['sd'][0]['type'], 'DX')
        self.assertEqual(result['dx'][0]['type'], 'SD')

    async def test_enrich_uses_correct_chart(self):
        p = self.player()
        records = [{'song_id': 123, 'type': t, 'level_index': 3, 'achievements': 100} for t in ('SD', 'DX')]
        await p._enrich_with_df(records)
        self.assertEqual([r['ds'] for r in records], [4, 8])
        self.assertEqual([r['df_song_id'] for r in records], ['123', '10123'])

    async def test_df_to_lxns_types_and_invalid_records(self):
        p = self.player()
        records = [{'song_id': sid, 'type': t, 'level_index': 3, 'achievements': 100} for sid,t in ((123,'SD'),(10123,'DX'),(123,'DX'),(123,''))]
        records += [{'song_id': 123, 'type': 'SD', 'level_index': 4, 'achievements': 100}]
        mapped, skipped, errors = await p._map_df_records(records)
        self.assertEqual([(r['id'],r['type']) for r in mapped], [(123,'standard'),(123,'dx')])
        self.assertEqual(skipped, 3)

    async def test_reverse_payload_keeps_types(self):
        p = self.player()
        p._lxns.get_user_scores.return_value = {'data': [{'id':123,'type':t,'level_index':3,'achievements':100} for t in ('standard','dx','unknown','')]}
        ok, data, err = await p.upload_lxns_to_df('synthetic')
        self.assertTrue(ok, err)
        payload = p._df.update_records.call_args.args[1]
        self.assertEqual([r['type'] for r in payload], ['SD', 'DX'])
        self.assertEqual(data['skipped'], 2)

    async def test_both_dry_runs_do_not_write(self):
        p = self.player()
        p._df.get_player_records.return_value = {'records':[{'song_id':10123,'title':'Dual','type':'DX','level_index':3,'achievements':100}]}
        p._lxns.get_user_scores.return_value = {'data':[{'id':123,'type':'dx','level_index':3,'achievements':99}]}
        for method in (p.upload_df_to_lxns, p.upload_lxns_to_df):
            ok, data, err = await method('synthetic', dry_run=True)
            self.assertTrue(ok, err)
            self.assertEqual(data['uploaded'], 0)
        p._df.update_records.assert_not_called()
        p._lxns.upload_user_scores.assert_not_called()

    async def test_target_read_failure_stops_sync(self):
        p = self.player()
        p._lxns.get_user_scores.return_value = {'data':[{'id':123,'type':'dx','level_index':3,'achievements':100}]}
        p._df.get_player_records.return_value = {'_error':'offline'}
        self.assertFalse((await p.upload_lxns_to_df('synthetic'))[0])
        p._df.update_records.assert_not_called()
        p._df.get_player_records.return_value = {'records':[{'song_id':10123,'type':'DX','level_index':3,'achievements':100}]}
        p._lxns.get_user_scores.return_value = {'_error':'offline'}
        self.assertFalse((await p.upload_df_to_lxns('synthetic'))[0])
        p._lxns.upload_user_scores.assert_not_called()

    async def test_single_song_best_queries_both_chart_types(self):
        p = self.player()
        p._resolve_song = AsyncMock(return_value=({'id':123,'title':'Dual','difficulties':{'standard':[{}],'dx':[{}]}},''))
        p._resolve_lxns = AsyncMock(return_value=({'X-User-Token':'synthetic'},''))
        async def best(auth, song_id, song_type):
            return {'data':[{'id':song_id,'type':song_type,'level_index':3,'achievements':100}]}
        p._lxns.get_user_bests.side_effect = best
        ok, data, err = await p.get_lxns_best('synthetic','Dual')
        self.assertTrue(ok,err)
        self.assertEqual([r['type'] for r in data['rows']], ['SD','DX'])

if __name__ == '__main__':
    unittest.main()
