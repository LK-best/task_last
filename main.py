from flask import Flask, render_template, redirect, abort, request
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from data import db_session
from data.users import User
from data.news import News
from data.jobs import Jobs
from data.departments import Departments
from forms.user import RegisterForm, LoginForm
from forms.job import AddJobForm
from forms.department import AddDepartmentForm
from data.category import Category

app = Flask(__name__)
app.config["SECRET_KEY"] = "yandexlyceum_secret_key"

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)

@app.route("/info")
def spisok():
    db = db_session.create_session()
    jobs = db.query(Jobs).all()
    return render_template("jobs.html", jobs=jobs)

@app.route('/departments')
def spisok2():
    db = db_session.create_session()
    departments = db.query(Departments).all()
    return render_template('departments.html', departments=departments)

@app.route('/', methods=['GET', 'POST'])
def login(): 
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/jobs")
        return render_template('login.html',
                               message="Wrong login or password",
                               form=form)
    return render_template('login.html', title='Authorization', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template(
                "register.html",
                title="Регистрация",
                form=form,
                message="Пароли не совпадают",
            )
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template(
                "register.html",
                title="Регистрация",
                form=form,
                message="Такой пользователь уже есть",
            )
        user = User(
            name=form.name.data,
            email=form.email.data,
            surname=form.surname.data,
            age=form.age.data,
            position=form.position.data,
            speciality=form.speciality.data,
            address=form.address.data
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect("/jobs")
    return render_template("register.html", title="Регистрация", form=form)

@app.route("/jobs", methods=["GET", "POST"])
@login_required
def add_job():
    form = AddJobForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        job = Jobs(
            job=form.job.data, 
            team_leader=form.team_leader.data,
            work_size=int(form.work_size.data), 
            collaborators=form.collaborators.data,
            is_finished=form.is_finished.data
        )
        db_sess.add(job)
        db_sess.commit()
        return redirect('/info')
    return render_template("register_for_the_job.html", title="Добавить работу", form=form)


@app.route("/register_for_department", methods=['GET', 'POST'])
@login_required
def add_department():
    form = AddDepartmentForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        department = Departments(
            title= form.title.data,
            chief = form.chief.data,
            members=form.members.data,
            email=form.email.data
        )
        db_sess.add(department)
        db_sess.commit()
        return redirect('departments')
    return render_template('register_for_the_department.html', title="Добавить департамент", form=form)


@app.route('/edit_department/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_department(id):
    form = AddDepartmentForm()
    db_sess = db_session.create_session()
    
    department = db_sess.query(Departments).filter(Departments.id == id).first()
    
    if not department:
        abort(404)

    if current_user.id != 1 and department.chief != current_user.id:
        abort(403)
        
    if request.method == "GET":
        form.title.data = department.title
        form.chief.data = department.chief
        form.members.data = department.members
        form.email.data = department.email

    if form.validate_on_submit():
        department.title = form.title.data
        department.chief = int(form.chief.data)
        department.members = form.members.data
        department.email = form.email.data
        
        db_sess.commit()
        return redirect('/departments')

    return render_template('register_for_the_department.html', title='Редактирование работы', form=form)


@app.route('/delete_department/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_department(id):
    db_sess = db_session.create_session()
    
    department = db_sess.query(Departments).filter(Departments.id == id).first()
    
    if not department:
        abort(404)

    if current_user.id != 1 and department.team_leader != current_user.id:
        abort(403)
    db_sess.delete(department)
    db_sess.commit()
    
    return redirect('/departments')


@app.route('/edit_job/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_job(id):
    print(id)
    form = AddJobForm()
    db_sess = db_session.create_session()
    
    job = db_sess.query(Jobs).filter(Jobs.id == id).first()
    
    if not job:
        abort(404)

    if current_user.id != 1 and job.team_leader != current_user.id:
        abort(403)
    if request.method == "GET":
        form.job.data = job.job
        form.team_leader.data = job.team_leader
        form.work_size.data = job.work_size
        form.collaborators.data = job.collaborators
        form.is_finished.data = job.is_finished

    if form.validate_on_submit():
        job.job = form.job.data
        job.team_leader = form.team_leader.data
        job.work_size = int(form.work_size.data)
        job.collaborators = form.collaborators.data
        job.is_finished = form.is_finished.data
        
        db_sess.commit()
        return redirect('/info')

    return render_template('register_for_the_job.html', title='Редактирование работы', form=form)

@app.route('/delete_job/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_job(id):
    db_sess = db_session.create_session()
    
    job = db_sess.query(Jobs).filter(Jobs.id == id).first()
    
    if not job:
        abort(404)

    if current_user.id != 1 and job.team_leader != current_user.id:
        abort(403)
    db_sess.delete(job)
    db_sess.commit()
    
    return redirect('/info')

def main():
    db_session.global_init("db/blogs.db")
    db_sess = db_session.create_session()

    if not db_sess.query(User).filter(User.id == 1).first():
        captain = User()
        captain.name = "Иван"
        captain.surname = "Капитан"
        captain.email = "cap@mars.org"
        captain.set_password("123")
        db_sess.add(captain)
        db_sess.commit()

    if not db_sess.query(User).filter(User.id == 2).first():
        leader = User()
        leader.name = "Пётр"
        leader.surname = "Лидер"
        leader.email = "leader@mars.org"
        leader.set_password("123")
        db_sess.add(leader)
        db_sess.commit()

    
    if not db_sess.query(Jobs).filter(Jobs.id == 1).first():
        job1 = Jobs(job="Ремонт модуля", team_leader=1, work_size=15, collaborators="2", is_finished=False)
        db_sess.add(job1)
        db_sess.commit()

    if not db_sess.query(Jobs).filter(Jobs.id == 2).first():
        job2 = Jobs(job="Анализ грунта", team_leader=2, work_size=5, collaborators="1", is_finished=True)
        db_sess.add(job2)
        db_sess.commit()
    if not db_sess.query(Departments).first():
        dep1 = Departments(
            title="Инженерный отдел", 
            chief=1, 
            members="2, 3", 
            email="eng@mars.org"
        )
        db_sess.add(dep1)
        
        dep2 = Departments(
            title="Научный отдел", 
            chief=2, 
            members="1", 
            email="sci@mars.org"
        )
        db_sess.add(dep2)
        
        db_sess.commit()
        print("Департаменты добавлены")
    
    if not db_sess.query(Category).first():
        cat1 = Category(name="Ремонт")
        cat2 = Category(name="Исследование")
        cat3 = Category(name="Обслуживание")

        db_sess.add(cat1)
        db_sess.add(cat2)
        db_sess.add(cat3)
        db_sess.commit()

    if not db_sess.query(Jobs).filter(Jobs.id == 1).first():
        job1 = Jobs(job="Ремонт модуля", team_leader=1, work_size=15, collaborators="2", is_finished=False)
        
        job1.categories.append(cat1)
        job1.categories.append(cat2)
        
        db_sess.add(job1)
        db_sess.commit()
    app.run()

if __name__ == "__main__":
    main()