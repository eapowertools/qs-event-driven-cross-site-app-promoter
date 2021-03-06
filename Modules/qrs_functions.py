"""
Helper functions, primarily for working with the QRS API.
"""

from datetime import datetime, timedelta
import os
import json
import uuid
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# configuration
with open("static/config.json") as f:
    CONFIG = json.load(f)
    f.close()

REMOTE_SERVERS = CONFIG["promote_on_custom_property_change"]["remote_servers"]
REMOTE_SERVER_ALIASES = [server["server_alias"].lower() for server in REMOTE_SERVERS]
USER_DIRECTORY = CONFIG["promote_on_custom_property_change"]["user_directory"]
USER_ID = CONFIG["promote_on_custom_property_change"]["user_id"]

if CONFIG["installed_on_sense_server"] == "true":
    LOCAL_SERVER = "localhost"
else:
    LOCAL_SERVER = CONFIG["local_server"]

# build URLs
LOCAL_BASE_URL = "https://" + LOCAL_SERVER + ":4242"


def establish_requests_session(server_location):
    """
    Setup session
    """
    s = requests.Session()

    if server_location.lower() == "local":
        cert_folder = "Certificates/LocalServerCerts"
        base_url = LOCAL_BASE_URL
    elif server_location.lower() in REMOTE_SERVER_ALIASES:
        cert_folder = "Certificates/" + server_location.lower()
        for server in REMOTE_SERVERS:
            if server["server_alias"].lower() == server_location.lower():
                base = server["remote_server"]
                base_url = "https://" + base + ":4242"
                break
    else:
        return "no matching alias"

    # set headers
    headers = {
        "X-Qlik-Xrfkey": "abcdefg123456789",
        "X-Qlik-User": "UserDirectory=" + USER_DIRECTORY + ";UserId=" + USER_ID,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36",
    }

    # add certs to headers
    s.headers.update(headers)
    s.cert = (cert_folder + "/client.pem", cert_folder + "/client_key.pem")
    s.verify = False

    return s, base_url


def close_requests_session(s):
    """
    Close session
    """
    # close the session
    s.close()


def app_full(s, base_url, app_id):
    """
    qrs/app/full
    """
    # get app full
    r = s.get(
        base_url + "/qrs/app/full?filter=id eq " + app_id + "&xrfkey=abcdefg123456789"
    )
    rjson = r.json()[0]

    return r.status_code, rjson


def stream_full(s, base_url, stream_id):
    """
    qrs/stream/full
    """
    r = s.get(
        base_url
        + "/qrs/stream/full?filter=id eq "
        + stream_id
        + "&xrfkey=abcdefg123456789"
    )
    rjson = r.json()[0]

    return r.status_code, rjson


def export_app(s, base_url, app_id, app_name, skip_data=False):
    """
    Export the app in two step process
    """
    temp_GUID = str(uuid.uuid4())
    if skip_data:
        r = s.post(
            base_url
            + "/qrs/app/"
            + app_id
            + "/export/"
            + temp_GUID
            + "?skipData=true&xrfkey=abcdefg123456789"
        )
    else:
        r = s.post(
            base_url
            + "/qrs/app/"
            + app_id
            + "/export/"
            + temp_GUID
            + "?xrfkey=abcdefg123456789"
        )

    rjson = r.json()
    download_path = str(rjson["downloadPath"])
    r = s.get(base_url + download_path, stream=True)

    with open("ExportedApps/" + app_name + ".qvf", "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
        f.close()

    return r.status_code


def upload_app(s, base_url, app_name):
    """
    qrs/app/upload
    """
    data = open("ExportedApps/" + app_name + ".qvf", "rb").read()
    r = s.post(
        base_url + "/qrs/app/upload?name=" + app_name + "&xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/vnd.qlik.sense.app"},
    )
    rjson = r.json()
    new_app_id = rjson["id"]

    return r.status_code, new_app_id


def get_remote_app_ids_by_name(s, base_url, app_name):
    """
    Looks up all apps by name and returns the json reponse
    """
    r = s.get(
        base_url
        + "/qrs/app/full?filter=name eq '"
        + app_name
        + "'&xrfkey=abcdefg123456789"
    )
    rjson = r.json()

    return r.status_code, rjson


def get_remote_stream_id_by_name(s, base_url, stream_name):
    """
    Gets a stream ID by its name
    """
    r = s.get(
        base_url
        + "/qrs/stream/full?filter=name eq '"
        + stream_name
        + "'&xrfkey=abcdefg123456789"
    )
    rjson = r.json()
    try:
        stream_id = rjson[0]["id"]
    except IndexError:
        stream_id = None

    return r.status_code, stream_id


def publish_to_stream(s, base_url, app_id, stream_id):
    """
    Publishes an app to a target stream
    """
    # publish the app
    r = s.put(
        base_url
        + "/qrs/app/"
        + app_id
        + "/publish?stream="
        + stream_id
        + "&xrfkey=abcdefg123456789"
    )

    return r.status_code


def app_replace(s, base_url, app_id, target_app_id):
    """
    Replaces a published app with another app
    """
    # replace the app
    r = s.put(
        base_url
        + "/qrs/app/"
        + app_id
        + "/replace?app="
        + target_app_id
        + "&xrfkey=abcdefg123456789"
    )

    return r.status_code


def app_delete(s, base_url, app_id):
    """
    Deletes an app
    """
    # delete the app
    r = s.delete(base_url + "/qrs/app/" + app_id + "?xrfkey=abcdefg123456789")

    return r.status_code


def duplicate_app(s, base_url, app_id, app_name):
    """
    Duplicates an app
    """
    # coppy the app
    r = s.post(
        base_url
        + "/qrs/app/"
        + app_id
        + "/copy?name="
        + app_name
        + "&xrfkey=abcdefg123456789"
    )
    rjson = r.json()
    dup_app_id = rjson["id"]

    return r.status_code, dup_app_id


def change_app_owner(s, base_url, app_id, owner_id):
    """
    Changes the owner of an app
    """
    rjson = app_full(s, base_url, app_id)[1]

    rjson["owner"] = dict({"id": owner_id})
    rjson["modifiedDate"] = str(
        ((datetime.today()) + timedelta(days=1)).isoformat() + "Z"
    )
    data = json.dumps(rjson)

    r = s.put(
        base_url + "/qrs/app/" + app_id + "?xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    return r.status_code


def delete_local_app_export(app_name):
    """
    Deletes the local copy of the app that
    was exported before being moved
    """
    try:
        os.remove("ExportedApps/" + app_name + ".qvf")
        return True
    except:
        return False


def modify_app_description(s, base_url, app_id, description):
    """
    Modifies the description of an app
    """
    rjson = app_full(s, base_url, app_id)[1]

    rjson["modifiedDate"] = str(
        ((datetime.today()) + timedelta(days=1)).isoformat() + "Z"
    )
    rjson["description"] = description

    data = json.dumps(rjson)

    r = s.put(
        base_url + "/qrs/app/" + app_id + "?xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    return r.status_code


def user_full(s, base_url, user_id):
    """
    qrs/user/full
    """
    # get app full
    r = s.get(base_url + "/qrs/user/" + user_id + "?xrfkey=abcdefg123456789")
    rjson = r.json()

    return r.status_code, rjson


def server_node_config_full(s, base_url):
    """
    qrs/servernodeconfiguration/full
    """
    # get the server nodes
    r = s.get(base_url + "/qrs/servernodeconfiguration/full?xrfkey=abcdefg123456789")
    rjson = r.json()

    return r.status_code, rjson


def service_cluster_full(s, base_url):
    """
    qrs/servicecluster/full
    """
    r = s.get(base_url + "/qrs/servicecluster/full?xrfkey=abcdefg123456789")
    rjson = r.json()[0]

    return r.status_code, rjson


def remove_props_from_app(s, base_url, app_id, prop_list):
    rjson = app_full(s, base_url, app_id)[1]
    custom_properties = rjson["customProperties"]

    custom_properties = list(
        filter(lambda x: (x["definition"]["name"] not in prop_list), custom_properties)
    )

    rjson["customProperties"] = custom_properties
    rjson["modifiedDate"] = str(
        ((datetime.today()) + timedelta(days=1)).isoformat() + "Z"
    )
    data = json.dumps(rjson)

    # put the app without the custom properties
    r = s.put(
        base_url + "/qrs/app/" + app_id + "?xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    return r.status_code


def get_tag_id_by_name(s, base_url, tag_name):
    r = s.get(
        base_url + "/qrs/tag?filter=name eq '" + tag_name + "'&xrfkey=abcdefg123456789"
    )
    rjson = r.json()
    tag_id = rjson[0]["id"]

    return r.status_code, tag_id


def add_tag_to_app(s, base_url, app_id, tag_name):
    # look up the current tags
    rjson = app_full(s, base_url, app_id)[1]
    tags = rjson["tags"]

    # get the id of the tag by name
    tag_id = get_tag_id_by_name(s, base_url, tag_name)[1]

    # add the tag
    if len(tags) > 0:
        tags.append({"id": tag_id})
    else:
        tags = [{"id": tag_id}]

    rjson["tags"] = tags
    rjson["modifiedDate"] = str(
        ((datetime.today()) + timedelta(days=1)).isoformat() + "Z"
    )
    data = json.dumps(rjson)

    # put the app without the tag
    r = s.put(
        base_url + "/qrs/app/" + app_id + "?xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    return r.status_code


def remove_tag_from_app(s, base_url, app_id, tag_name):
    # look up the current tags
    rjson = app_full(s, base_url, app_id)[1]
    tags = rjson["tags"]

    # get the id of the tag by name
    tag_id = get_tag_id_by_name(s, base_url, tag_name)[1]

    # remove the tag
    tags = list(filter(lambda x: (x["id"] != tag_id), tags))

    rjson["tags"] = tags
    rjson["modifiedDate"] = str(
        ((datetime.today()) + timedelta(days=1)).isoformat() + "Z"
    )
    data = json.dumps(rjson)

    # put the app without the tag
    r = s.put(
        base_url + "/qrs/app/" + app_id + "?xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    return r.status_code

