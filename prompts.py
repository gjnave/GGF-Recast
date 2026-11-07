"""Original GGF prompt construction using the publisher's section names."""

def image_prompt(cast,plans=None):
    mappings=[]
    for n,entry in enumerate(cast,2):
        plan=(plans or [{}]*len(cast))[n-2]
        source=entry['source']+' ('+plan['source_identity']+')' if plan.get('source_identity') else entry['source']
        target=plan.get('target_identity') or entry['description']
        frame=str(plan.get('framing','')).lower()
        if 'close' in frame:
            framing='a face close-up at the source face size and position; the replacement face fills the same crop, no full body'
        elif 'waist' in frame or 'upper' in frame or 'medium' in frame:
            framing='the same upper-body crop, size and position as the selected source subject'
        else:
            framing='the exact source camera crop, subject scale and subject position, without zooming, centering or rearranging the scene'
        mappings.append(f'In image 1, completely remove {source}. Replace that entire subject with {target} from image {n}. '
                        'Remove the original head, face, hair, body, costume, limbs, shoes, accessories and outline. '
                        f'Image {n} supplies identity and clothing only; ignore its background, text, other people and pose. '
                        f'The replacement must adopt the source pose: {plan.get("source_pose","the original subject position, arm and leg positions, expression and orientation")}. '
                        f'The output framing must remain: {framing}.')
    return ('Edit image 1 into one integrated scene. '+ ' '.join(mappings)+
            ' Rebuild each replacement as one anatomically coherent character, with its own body and clothing.'
            ' Generate any needed body parts that are outside the reference photo. Match the source performance, not the reference pose.'
            ' The original replaced subject must be completely absent. No old helmet, robot parts, limbs, shoes or silhouette may remain behind the replacement.'
            ' Reconstruct newly uncovered background naturally. Keep the camera, lighting, setting and every unselected character unchanged in its exact original location.'
            ' Keep the same number of characters as image 1. Edit only the selected subject in place.'
            ' Do not paste a photo or add a person in front of the original. Return only the edited scene.')

def video_prompt(cast,request,reference_count=1,appearance_only=False):
    subjects=[]
    for i,entry in enumerate(cast,1):
        subjects.append(f'<Subject {i}> is the replacement for {entry["source"]}: {entry["description"]}. Its appearance is shown in the supplied target pictures.')
    pictures='\n'.join(f'<Picture {i}> shows the intended edited scene at a known moment of <Video 1>.' for i in range(1,reference_count+1))
    if appearance_only:
        pictures = ('<Picture 1> defines the faces, clothes and accessories for the entire clip. '
                    'Use the motion, pose, framing and background from <Video 1> throughout.')
    return ('subject_definitions:\n<Video 1> contains the original scene, camera movement and performances.\n'+pictures+'\n'+'\n'.join(subjects)+
            '\n\nsummary:\nThe video shows the assigned replacement characters performing the original actions. '+request+
            '\n\nretention_analysis:\nThe source composition, choreography, camera path, props and timing remain consistent.'
            ' The replacement characters keep the faces, hair, bodies and outfits shown in the target pictures.'
            ' Replace the entire assigned subject, including its silhouette, limbs and accessories; no original costume or body parts remain behind it.'
            '\n\ndetailed_description:\n[Shot 1] The characters occupy the same positions and follow the same movements as the original performers.'
            ' Their appearance matches the target pictures throughout the shot. People without replacement assignments remain unchanged.'
            ' Speech and singing retain the original mouth timing. The original replaced appearances do not return.'
            '\n\noverall_soundscape:\nThe original source soundtrack continues in sync.'
            '\n\nnon_diegetic_music:\nAny music already in the source is retained.')
