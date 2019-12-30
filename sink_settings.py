bz_application_key_id = 'BackblazeKeyIdHere'
bz_application_key = 'BackBlazeKey'
bz_bucket_name = 'BackBlazeBucketName'
bz_unprocessed_folder_name = 'FolderNameForUnProcessedFiles'
accounts_to_sub = [{'account_id': 'KazooAccountIdHere', 'sub_descendants': True,
                     'api_key': 'ApiKeyHere'}]
events_to_sub = ["call.*.*", "qubicle.session", "qubicle.queue", "qubicle.recipient"]
api_base_url = 'https://ui.zswitch.net/v2'
ws_base_url = 'wss://api.zswitch.net:5443/'
ca_pem = 'cacert.pem'