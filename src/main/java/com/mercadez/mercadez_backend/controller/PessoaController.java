package com.mercadez.mercadez_backend.controller;

import com.mercadez.mercadez_backend.entity.Pessoa;
import com.mercadez.mercadez_backend.repository.PessoaRepository;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/pessoas")
@CrossOrigin(origins = "*")
public class PessoaController {

    private final PessoaRepository repository;

    public PessoaController(PessoaRepository repository) {
        this.repository = repository;
    }

    // LISTAR
    @GetMapping
    public List<Pessoa> listar() {
        return repository.findAll();
    }

    // CADASTRAR
    @PostMapping
    public Pessoa salvar(@RequestBody Pessoa pessoa) {
        return repository.save(pessoa);
    }
}
