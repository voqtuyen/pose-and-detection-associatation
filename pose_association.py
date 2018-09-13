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
agrs = parser.parse_args()

anno_dir = agrs.anno_dir
kpts_dir = agrs.keypoint_dir

_LIST_BNDB_DETECTIONS = []
_LIST_BNDB_KEYPOINTS = []


def _visualize_bndboxes_overlap(ktps_bbox, det_bbox, plot_title='bboxes overlap visualization'):
    img = np.zeros((800,800,3), np.uint8)
    cv2.rectangle(img, (ktps_bbox[0], ktps_bbox[1]), (ktps_bbox[2], ktps_bbox[3]), (255,0,0),3)
    cv2.rectangle(img, (det_bbox[0], det_bbox[1]), (det_bbox[2], det_bbox[3]), (0,255,0),3)
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

    for elem in root:
        if elem.tag == 'object':
            for subelem in elem:
                if subelem.tag == 'pose':
                    list_poses.append(subelem.text)
    return list_poses

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

def prettify(elem):
    """
    Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf8')
    root = etree.fromstring(rough_string)
    return etree.tostring(root, pretty_print=True, encoding='utf-8').replace(" ".encode(), "\t".encode())

def _associate_poses_to_dets(dir, filename, poses):
    tree = ET.parse(os.path.join(dir, filename))
    root = tree.getroot()
    indx = 0
    for elem in root:
        if elem.tag == 'object':
            has_pose_tag = False
            for subelem in elem:
                if subelem.tag == 'pose':
                    has_pose_tag = True 
                    subelem.text = poses[indx]     
            if not has_pose_tag:
                pose_elem = ET.SubElement(elem, 'pose')
                pose_elem.text = poses[indx]
            indx += 1
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
        if len(_LIST_BNDB_DETECTIONS) == len(_LIST_BNDB_KEYPOINTS):

            inters = _intersection(_LIST_BNDB_DETECTIONS, _LIST_BNDB_KEYPOINTS)
            inters_idx = np.argmax(inters, axis=0)
            poses = _get_pose_from_one_xml(kpts_dir, anno_file)
            poses = np.take(poses, inters_idx)
            _associate_poses_to_dets(anno_dir, anno_file, poses)
        else:
            print("Skip file " + str(anno_file) + " due to mismatch of #detected det to #poses")
