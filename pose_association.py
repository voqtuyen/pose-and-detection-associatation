import os
import argparse
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement
from lxml import etree
import codecs
import numpy as np
import cv2

# Command-line argument
parser = argparse.ArgumentParser()
parser.add_argument('--anno_dir', default='./annotations', help="Path to the annotation directory")
parser.add_argument('--keypoint_dir', default='./keypoints', help="Path to keypoints xml directory")
parser.add_argument('--plot_bboxes', default=False, help="Visualize the bounding boxes")
agrs = parser.parse_args()

anno_dir = agrs.anno_dir
kpts_dir = agrs.keypoint_dir
plot_bboxes = agrs.plot_bboxes

_LIST_BNDB_DETECTIONS = []
_LIST_BNDB_KEYPOINTS = []
_NUMBER_OF_KPTS_VALUE = 36


def _visualize_bndboxes_overlap(ktps_bboxes, det_bboxes, plot_title='bboxes overlap visualization'):
    img = np.ones((800,800,3), np.uint8) *255
    cv2.putText(img,plot_title,(10, 760), cv2.FONT_HERSHEY_SIMPLEX,1.0,(0,0,0))
    for i in range(len(ktps_bboxes)):
        cv2.rectangle(img, (ktps_bboxes[i][0], ktps_bboxes[i][1]), (ktps_bboxes[i][2], ktps_bboxes[i][3]), (20*i,255-10*i,255-10*i),1)
        cv2.putText(img, 'k' + str(i),(ktps_bboxes[i][0], ktps_bboxes[i][1]), cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,0,0))
    for j in range(len(det_bboxes)):
        cv2.rectangle(img, (det_bboxes[j][0], det_bboxes[j][1]), (det_bboxes[j][2], det_bboxes[j][3]), (20*j,10*j,255-10*j),1)
        cv2.putText(img,'d' + str(j),(det_bboxes[j][2], det_bboxes[j][3]), cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,0,0))
    cv2.imshow(plot_title,img)
    cv2.waitKey(0)

def _get_bndbox_coordinates_from_one_xml(dir, filename):
    """ 
    Read bboxes from an input xml file and store it to the list of list(bbox)
    Arguments: 
        dir: path to the directory containing the file
        filename: name of the xml file
    Returns:
        list of detected bounding boxes
    """
    tree = ET.parse(os.path.join(dir, filename))
    root = tree.getroot()
    list_bboxes = []
    # Get all bounding boxes and store it as an array of structure [[bbox1], [bbox2]]
    for elem in root:
        if elem.tag == 'object':
            for subelem in elem:
                bndboxes = []
                if subelem.tag == 'bndbox':
                    for attr in subelem:
                        bndboxes.append(int(attr.text))
                    list_bboxes.append(bndboxes)

    return list_bboxes

def _get_pose_from_one_xml(dir, filename):
    """
    Traverse and get all poses from objects in the given xml
    Arguments:
        dir: path to the directory containing the file
        filename: name of the xml file
    Returns:
        list of all poses
    """
    tree = ET.parse(os.path.join(dir, filename))
    root = tree.getroot()
    list_poses = []
    list_kpts = []

    for elem in root:
        if elem.tag == 'object':
            for subelem in elem:
                if subelem.tag == 'pose':
                    list_poses.append(subelem.text)
                elif subelem.tag == 'keypoints':
                    list_kpts.append(subelem.text)
    return (list_poses, list_kpts)

def _intersection(pose_list, det_list):
    """
    Compute intersection of each element in the first list with every element of the second list
    Arguments:
        pose_list: python list of N bounding boxes surrounding the keypoints
        det_list: python list of N bounding boxes detected
    Returns:
        a np array with shape [N, N] representing pairwise intersections
    """
    np_det_arr = np.array(det_list)
    np_pose_arr = np.array(pose_list)

    x_min1, y_min1, x_max1, y_max1 = np.split(np_pose_arr, indices_or_sections=4, axis=1)
    x_min2, y_min2, x_max2, y_max2 = np.split(np_det_arr, indices_or_sections=4, axis=1)

    all_pairs_min_ymax = np.minimum(y_max1, np.transpose(y_max2))
    all_pairs_max_ymin = np.maximum(y_min1, np.transpose(y_min2))
    intersect_heights = np.maximum(0.0, all_pairs_min_ymax - all_pairs_max_ymin)
    all_pairs_min_xmax = np.minimum(x_max1, np.transpose(x_max2))
    all_pairs_max_xmin = np.maximum(x_min1, np.transpose(x_min2))
    intersect_widths = np.maximum(0.0, all_pairs_min_xmax - all_pairs_max_xmin)

    return intersect_heights * intersect_widths

def _area(bbox_list):
    """
    Calculate the areas of bbox_list
        Before squeezing (shape=(2,1)):
            [[ 9][16]]
        After squeezing (shape=(2,)): 
            [ 9 16]
    Arguments: 
        bbox_list: list of boxes with top-left corner coordinates and bottom-up corner coordinates
    Return:
        list of the same size containing the areas of the bbox list
    """
    y_min, x_min, y_max, x_max = np.split(np.array(bbox_list), indices_or_sections=4, axis=1)
    return (y_max - y_min) * (x_max - x_min)

def prettify(elem):
    """
    Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf8')
    root = etree.fromstring(rough_string)
    return etree.tostring(root, pretty_print=True, encoding='utf-8').replace(" ".encode(), "\t".encode())

def _associate_poses_to_dets(dir, filename, poses, kpts):
    """
    Run association between dets and poses
    Arguments:
        - dir: path to the directory containing the det xml files
        - filename: name of the det file
        - poses: list of poses, order is the same as order in the pose xml generated by pose annotation tool
    Returns:
        override xml file with added pose information
    """
    tree = ET.parse(os.path.join(dir, filename))
    root = tree.getroot()

    def handle_adding_xml_elem(elem_name, value_list):
        idx = 0
        for elem in root:
            if elem.tag == 'object':
                has_pose_tag = False
                for subelem in elem:
                    if subelem.tag == elem_name:
                        has_pose_tag = True 
                        subelem.text = value_list[idx]     
                if not has_pose_tag:
                    pose_elem = ET.SubElement(elem, elem_name)
                    pose_elem.text = value_list[idx]
                idx += 1

    handle_adding_xml_elem('pose', poses)
    handle_adding_xml_elem('keypoints', kpts)

    out_file = codecs.open(os.path.join(dir, filename), 'w', encoding='utf-8')
    out_file.write(prettify(root).decode('utf-8'))
    out_file.close()        
            
if __name__ == '__main__':

    num_files_in_anno_dir = len([name for name in os.listdir(anno_dir)])
    num_files_in_kpts_dir = len([name for name in os.listdir(kpts_dir)])
    if not num_files_in_anno_dir == num_files_in_kpts_dir:
        raise ValueError("Number of xml files in annotation dir and that in keypoints dir are different!!!")

    anno_files = [name for name in os.listdir(anno_dir)]

    for anno_file in anno_files:
        # Get lists of bounding boxes from pose xml and detection xml
        _LIST_BNDB_DETECTIONS = _get_bndbox_coordinates_from_one_xml(anno_dir, anno_file)
        _LIST_BNDB_KEYPOINTS = _get_bndbox_coordinates_from_one_xml(kpts_dir, anno_file)
        inters = _intersection(_LIST_BNDB_DETECTIONS, _LIST_BNDB_KEYPOINTS)
        areas = np.tile(_area(_LIST_BNDB_DETECTIONS), (1, len(_LIST_BNDB_KEYPOINTS)))
        inters = np.divide(inters, areas)
        
        poses, kpts = _get_pose_from_one_xml(kpts_dir, anno_file)

        if len(_LIST_BNDB_DETECTIONS) <= len(_LIST_BNDB_KEYPOINTS):
            inters_idx = np.argmax(inters, axis=1)
            poses = np.take(poses, inters_idx)
            kpts = np.take(kpts, inters_idx)
            _associate_poses_to_dets(anno_dir, anno_file, poses, kpts)
        else:
            inters_idx = np.argmax(inters,axis=0)
            poses_tmp = np.array(["Unspecified"] * len(_LIST_BNDB_DETECTIONS))
            kpts_tmp = np.array(np.zeros(_NUMBER_OF_KPTS_VALUE) * len(_LIST_BNDB_DETECTIONS))
            for idx, idx_value in enumerate(inters_idx):
                poses_tmp[idx_value] = poses[idx]
                kpts_tmp[idx_value] = kpts[idx]
            _associate_poses_to_dets(anno_dir, anno_file, poses_tmp, kpts)
        if plot_bboxes:
            _visualize_bndboxes_overlap(_LIST_BNDB_KEYPOINTS, _LIST_BNDB_DETECTIONS, anno_file)
