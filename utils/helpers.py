import pandas as pd
import numpy as np
import joblib
from config.paths_config import *

############# 1. GET_ANIME_FRAME

def getAnimeFrame(anime,path_df):
    print(f"[getAnimeFrame] Called with anime={anime}")
    df = pd.read_csv(path_df)
    if isinstance(anime,int):
        print(f"[getAnimeFrame] Searching by anime_id={anime}")
        return df[df.anime_id == anime]
    if isinstance(anime,str):
        print(f"[getAnimeFrame] Searching by eng_version='{anime}'")
        return df[df.eng_version == anime]
    

########## 2. GET_SYNOPSIS

def getSynopsis(anime,path_synopsis_df):
    print(f"[getSynopsis] Called with anime={anime}")
    synopsis_df = pd.read_csv(path_synopsis_df)
    if isinstance(anime,int):
        print(f"[getSynopsis] Searching by MAL_ID={anime}")
        return synopsis_df[synopsis_df.MAL_ID == anime].sypnopsis.values[0]
    if isinstance(anime,str):
        print(f"[getSynopsis] Searching by Name='{anime}'")
        return synopsis_df[synopsis_df.Name == anime].sypnopsis.values[0]


########## 3. CONTENT RECOMMENDATION

def find_similar_animes(name, path_anime_weights, path_anime2anime_encoded, path_anime2anime_decoded, path_anime_df, n=10, return_dist=False, neg=False):
    print(f"[find_similar_animes] Called with name='{name}', n={n}, return_dist={return_dist}, neg={neg}")
    anime_weights = joblib.load(path_anime_weights)
    anime2anime_encoded = joblib.load(path_anime2anime_encoded)
    anime2anime_decoded = joblib.load(path_anime2anime_decoded)

    index = getAnimeFrame(name, path_anime_df).anime_id.values[0]
    print(f"[find_similar_animes] Anime ID resolved: {index}")
    encoded_index = anime2anime_encoded.get(index)

    if encoded_index is None:
        print("[find_similar_animes] Encoded index not found!")
        raise ValueError(f"Encoded index not found for anime ID: {index}")

    dists = np.dot(anime_weights, anime_weights[encoded_index])
    sorted_dists = np.argsort(dists)

    n = n + 1

    if neg:
        print("[find_similar_animes] Getting least similar animes")
        closest = sorted_dists[:n]
    else:
        print("[find_similar_animes] Getting most similar animes")
        closest = sorted_dists[-n:]

    if return_dist:
        print("[find_similar_animes] Returning raw distances and indices")
        return dists, closest

    SimilarityArr = []
    for close in closest:
        decoded_id = anime2anime_decoded.get(close)
        anime_frame = getAnimeFrame(decoded_id, path_anime_df)
        anime_name = anime_frame.eng_version.values[0]
        genre = anime_frame.Genres.values[0]
        similarity = dists[close]

        SimilarityArr.append({
            "anime_id": decoded_id,
            "name": anime_name,
            "similarity": similarity,
            "genre": genre,
        })

    Frame = pd.DataFrame(SimilarityArr).sort_values(by="similarity", ascending=False)
    print("[find_similar_animes] Recommendation frame constructed")
    return Frame[Frame.anime_id != index].drop(['anime_id'], axis=1)


######## 4. FIND_SIMILAR_USERS

# def find_similar_users(item_input , path_user_weights , path_user2user_encoded , path_user2user_decoded, n=10 , return_dist=False,neg=False):
#     print(f"[find_similar_users] Called with user_id={item_input}, n={n}, return_dist={return_dist}, neg={neg}")
#     try:
#         user_weights = joblib.load(path_user_weights)
#         user2user_encoded = joblib.load(path_user2user_encoded)
#         user2user_decoded = joblib.load(path_user2user_decoded)

#         index = item_input
#         encoded_index = user2user_encoded.get(index)
#         dists = np.dot(user_weights, user_weights[encoded_index])
#         sorted_dists = np.argsort(dists)

#         n = n + 1

#         if neg:
#             print("[find_similar_users] Getting least similar users")
#             closest = sorted_dists[:n]
#         else:
#             print("[find_similar_users] Getting most similar users")
#             closest = sorted_dists[-n:]

#         if return_dist:
#             print("[find_similar_users] Returning raw distances and indices")
#             return dists, closest
        
#         SimilarityArr = []
#         for close in closest:
#             similarity = dists[close]
#             if isinstance(item_input,int):
#                 decoded_id = user2user_decoded.get(close)
#                 SimilarityArr.append({
#                     "similar_users" : decoded_id,
#                     "similarity" : similarity
#                 })

#         similar_users = pd.DataFrame(SimilarityArr).sort_values(by="similarity",ascending=False)
#         similar_users = similar_users[similar_users.similar_users != item_input]
#         print("[find_similar_users] Similar users DataFrame created")
#         return similar_users
#     except Exception as e:
#         print(f"Error Occured in find_similar_users {e}")

def find_similar_users(item_input, path_user_weights, path_user2user_encoded, path_user2user_decoded, n=10, return_dist=False, neg=False):
    """
    Finds users similar to a given user based on interaction embeddings.
    """
    print(f"[find_similar_users] Called with user_id={item_input}, n={n}, return_dist={return_dist}, neg={neg}")
    
    try:
        # Load data
        user_weights = joblib.load(path_user_weights)  # Shape: (num_users, 128)
        user2user_encoded = joblib.load(path_user2user_encoded)
        user2user_decoded = joblib.load(path_user2user_decoded)

        valid_users = list(user2user_encoded.keys())
        print(f"[Valid Users] Total: {len(valid_users)}\nUser IDs: {valid_users}")

        # Get encoded index of input user
        encoded_index = user2user_encoded.get(item_input)
        if encoded_index is None:
            print(f"[find_similar_users] Encoded index not found for user_id={item_input}")
            return pd.DataFrame(columns=["similar_users", "similarity"])

        # Get target embedding vector and squeeze to ensure correct shape
        target_vector = np.squeeze(user_weights[encoded_index])
        if target_vector.shape != (user_weights.shape[1],):
            raise ValueError(f"[find_similar_users] Unexpected shape for user embedding: {target_vector.shape}")

        # Compute cosine similarity using dot product
        dists = np.dot(user_weights, target_vector)
        sorted_dists = np.argsort(dists)
        n = n + 1  # Include the user itself in case it's in the top-N

        # Select closest or farthest users
        if neg:
            closest = sorted_dists[:n]
        else:
            closest = sorted_dists[-n:]

        # Return raw distances and indices if requested
        if return_dist:
            return dists, closest

        # Prepare results
        SimilarityArr = []
        for close in closest:
            decoded_id = user2user_decoded.get(close)
            similarity = dists[close]

            if decoded_id is not None and decoded_id != item_input:
                SimilarityArr.append({
                    "similar_users": decoded_id,
                    "similarity": similarity
                })

        similar_users_df = pd.DataFrame(SimilarityArr).sort_values(by="similarity", ascending=False)
        print(f"[find_similar_users] Found {len(similar_users_df)} similar users")
        return similar_users_df

    except Exception as e:
        print(f"[find_similar_users] Error occurred: {e}")
        return pd.DataFrame(columns=["similar_users", "similarity"])


################## 5. GET USER PREF

def get_user_preferences(user_id , path_rating_df , path_anime_df ):
    print(f"[get_user_preferences] Called with user_id={user_id}")
    rating_df = pd.read_csv(path_rating_df)
    df = pd.read_csv(path_anime_df)

    animes_watched_by_user = rating_df[rating_df.user_id == user_id]
    user_rating_percentile = np.percentile(animes_watched_by_user.rating , 75)

    animes_watched_by_user = animes_watched_by_user[animes_watched_by_user.rating >= user_rating_percentile]
    top_animes_user = (
        animes_watched_by_user.sort_values(by="rating" , ascending=False).anime_id.values
    )

    anime_df_rows = df[df["anime_id"].isin(top_animes_user)]
    anime_df_rows = anime_df_rows[["eng_version","Genres"]]

    print("[get_user_preferences] User preference DataFrame created")
    return anime_df_rows


######## 6. USER RECOMMENDATION

def get_user_recommendations(similar_users , user_pref ,path_anime_df , path_synopsis_df, path_rating_df, n=10):
    print(f"[get_user_recommendations] Called with {len(similar_users)} similar users")
    recommended_animes = []
    anime_list = []

    for user_id in similar_users.similar_users.values:
        pref_list = get_user_preferences(int(user_id) , path_rating_df, path_anime_df)
        pref_list = pref_list[~pref_list.eng_version.isin(user_pref.eng_version.values)]

        if not pref_list.empty:
            anime_list.append(pref_list.eng_version.values)

    if anime_list:
        anime_list = pd.DataFrame(anime_list)
        sorted_list = pd.DataFrame(pd.Series(anime_list.values.ravel()).value_counts()).head(n)

        for i,anime_name in enumerate(sorted_list.index):
            n_user_pref = sorted_list[sorted_list.index == anime_name].values[0][0]

            if isinstance(anime_name,str):
                frame = getAnimeFrame(anime_name,path_anime_df)
                anime_id = frame.anime_id.values[0]
                genre = frame.Genres.values[0]
                synopsis = getSynopsis(int(anime_id),path_synopsis_df)

                recommended_animes.append({
                    "n" : n_user_pref,
                    "anime_name" : anime_name,
                    "Genres" : genre,
                    "Synopsis": synopsis
                })
    print("[get_user_recommendations] Final recommendations generated")
    return pd.DataFrame(recommended_animes).head(n)
