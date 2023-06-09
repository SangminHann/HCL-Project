import detectFunc as df
import numpy as np
import webbrowser
import cv2
import os

# 화면 자르기 (중앙선 제일 위 s, 아래 e, 좌우 넓이 w)
def page_cut(page,s,e,w):
    left =  page[s+2:e, :w-2]
    right= page[s+2:e, w+2:w+w]

    return right, left

# 화면 자르기 전처리
def make(image):
    h=[]
    w=[]
    img_gray = df.convert2gray(image)
    thres = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]

    edgesx = cv2.Sobel(thres, -1, 1, 0, scale=4)
    edgesy = cv2.Sobel(thres, -1, 0, 1, scale=4)
    edges = cv2.addWeighted (edgesx, 1, edgesy, 1, 0)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 300,minLineLength=600,maxLineGap = 90)

    # 모의고사 상단 선, 중간 선 검출
    for i in range(len(lines)):
        for x1,y1,x2,y2 in lines[i]:
            if y1 == y2:
                h.append([x1,y1])
                h.append([x2,y2])

            if x1==x2:
                w.append([x1,y1])
                w.append([x2,y2])

    #가로선 h
    high=min(h, key=lambda x:x[1])
    max_h=max(h, key=lambda x:x[1]==high[1])

    #세로선 w
    max_w=max(w, key=lambda x:x[1])
    min_w=min(w, key=lambda x:x[1])

    cv2.line(image, min_w, max_w, (0,0,255), 1)

    right, left = page_cut(image,max_h[1], max_w[1], max_w[0])

    return right, left

# 문제 영역 찾기(좌우잘린 원본문제)
def findQuestionArea(page_rl):

    img_gray = df.convert2gray(page_rl)

    edge = cv2.Canny(img_gray, 100, 200) # imgray에 threshold넣는거인가?
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(1000,100))
    closed = cv2.morphologyEx(edge, cv2.MORPH_DILATE, kernel)
    contours, hierarchy = cv2.findContours(closed.copy(),cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    #만들어진 좌우 페이지에 문제 영역 표시
    cv2.drawContours(page_rl, contours, -1, (0,255,0), 1)

    return (contours)

# pdf파일 형식의 채점된 문제지에서 /혹은 X모양 찾기(좌우로 잘린 풀이된 문제)
def findCross(page_rl):

    dx = df.detectEdgeBySobel(page_rl, 30)

    lines = cv2.HoughLinesP(dx,1, np.pi/180,50,minLineLength=50,maxLineGap = 200)
    if lines is not None:
        for i in lines:
            cv2.line(page_rl, (int(i[0][0]), int(i[0][1])), (int(i[0][2]), int(i[0][3])), (255, 0, 0), 2)

    return lines

# 채점된 문제지의 사진을 /혹은 X모양 찾기(좌우로 잘린 풀이된 문제)
def findCrossInPic(page_rl):

    dx = df.detectEdgeBySobel(page_rl, 200)

    lines = cv2.HoughLinesP(dx,1, np.pi/180,50,minLineLength=48,maxLineGap =300)

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(page_rl, (x1, y1), (x2, y2), (255,0,0), 2)


    return lines

# 사각형이 겹치는지 확인
def is_rec_overlap(r1, r2):
    tmp1 = r1
    tmp2 = r2

    if r1[1] < r1[3]:
        tmp1[3] = r1[1]
        tmp1[1] = r1[3]

    if r2[1] < r2[3]:
        tmp2[3] = r2[1]
        tmp2[1] = r2[3]

    max_lb_x = max(tmp1[0], tmp2[0])
    min_lb_y = min(tmp1[1], tmp2[1])
    min_rt_x = min(tmp1[2], tmp2[2])
    max_rt_y = max(tmp1[3], tmp2[3])
    if max_lb_x > min_rt_x or min_lb_y < max_rt_y:
        return False
    return True

# 대각선 양 끝점으로 사각형 만들기
def make_rec(lines):
    if lines is None : return None
    rect=[]
    for line in lines:
        flag = True
        if rect == None:
            rect = line[0]
        else:
            for r in rect:
                if is_rec_overlap(line[0],r):
                    flag = False
                if flag is False:
                    break
            if flag:
                rect.append(line[0])

    return rect

# 틀린 문제 영역 찾기
def findWrong(count, rec, page):
    if rec is None: return None
    cnt_rst = []
    for c in count:
        flag = False
        x, y, w, h = cv2.boundingRect(c)
        rec_c = [x, y + h, x + w, y]
        for r in rec:

            if is_rec_overlap(rec_c, r):
                flag = True
            if flag:
                cnt_rst.append(c)
                break
    # 확인용 코드 틀린 문제영역 빨간색으로 표시
    # cv2.drawContours(page, cnt_rst, -1, (0,0,255), 1)
    cv2.drawContours(page, cnt_rst, -1, (255,255,255), 1)
    return cnt_rst #틀린문제 좌표

# picture과 orgin의 유사도 출력
def templete_match(origin, picture):

    methods = ['cv2.TM_CCOEFF_NORMED']

    for i, method_name in enumerate(methods):
        method = eval(method_name) # 문자열을 함수에 사용하도록 변환

        # 템플릿 매칭
        res = cv2.matchTemplate(picture, origin, method)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            match_val = min_val # 최소값(좋은 매칭)

        else:
            match_val = max_val # 최대값(좋은 매칭)

    return match_val

# 채점된 이미지파일로 원본 이미지파일 찾기
def find_origin(origin_dir, draw):
    val_list = []

    for origin in os.listdir(origin_dir) :
        # if template_file.startswith("test"):
        # startswitch는 origin_dir 내부에 원본 이미지 외에 다른 폴더나
        # 다른 이미지가 같이섞여있으면 특정 텍스트 포함한 이미지만 추출
        origin_path = os.path.join(origin_dir,origin)
        origin_img = cv2.imread(origin_path)
        val= templete_match(origin_img, draw)
        val_list.append((val,origin_img))

    # print(val_list)

    val_list.sort(reverse=True)

    #내림차순 정렬한 튜플에서 image 반환
    return val_list[0][1]

# 틀린 문제파일들을 지움
def deleteAllFiles(directory):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

# 채점된 이미지 파일에서 틀린 문제들을 뽑아내 ./test/wrong 디렉토리에 저장 (pdf)
def trimWrongImg(image_path):

    draw = cv2.imread(image_path)
    origin = find_origin("./test/origin/",draw)

    o_right,o_left=make(origin)
    d_right,d_left=make(draw)


    line_r = findCross(d_right)
    line_l = findCross(d_left)
    rect_r = make_rec(line_r)
    rect_l = make_rec(line_l)

    count_l = findQuestionArea(o_left)
    count_r = findQuestionArea(o_right)
    wrong_l = findWrong(count_l, rect_l, o_left)
    wrong_r = findWrong(count_r, rect_r, o_right)

    file_name = './test/wrong/wrong_'
    num = '1'
    suffix = '.png'

    if wrong_l is not None:
        for wrong in wrong_l:
            x, y, w, h = cv2.boundingRect(wrong)
            img = o_left[y: y + h, x : x + w]
            cv2.imwrite(file_name + num + suffix, img)
            num = str(int(num) + 1)
    if wrong_r is not None:
        for wrong in wrong_r:
            x, y, w, h = cv2.boundingRect(wrong)
            img = o_right[y: y + h, x : x + w]
            cv2.imwrite(file_name + num + suffix, img)
            num = str(int(num) + 1)

    num = str(int(num) - 1)
    return int(num)

# 채점된 이미지 파일에서 틀린 문제들을 뽑아내 ./test/wrong 디렉토리에 저장 (사진)
def trimWrongPic(img_path):
    
    picture_draw = cv2.imread(img_path)
    picture_draw = cv2.resize(picture_draw, dsize=(841,1190))
    
    picture = find_origin("./test/origin",picture_draw)
    picture = cv2.resize(picture, dsize=(841,1190))
    
    p_right,p_left=make(picture)
    pd_right,pd_left=make(picture_draw)
    
    count_pl = findQuestionArea(p_left)
    count_pr = findQuestionArea(p_right)

    line_pr = findCrossInPic(pd_right)
    line_pl = findCrossInPic(pd_left)

    rect_pr = make_rec(line_pr)
    rect_pl = make_rec(line_pl)

    wrong_l = findWrong(count_pl, rect_pl, p_left)
    wrong_r = findWrong(count_pr, rect_pr, p_right)
    
    file_name = './test/wrong/wrong_'
    num = '1'
    suffix = '.png'

    if wrong_l is not None:
        for wrong in wrong_l:
            x, y, w, h = cv2.boundingRect(wrong)
            img = p_left[y: y + h, x : x + w]
            cv2.imwrite(file_name + num + suffix, img)
            num = str(int(num) + 1)
            
    if wrong_r is not None:
        for wrong in wrong_r:
            x, y, w, h = cv2.boundingRect(wrong)
            img = p_right[y: y + h, x : x + w]
            cv2.imwrite(file_name + num + suffix, img)
            num = str(int(num) + 1)

    num = str(int(num) - 1)
    return int(num)
